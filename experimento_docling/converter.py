"""Experimento de conversao local de PDF com Docling. Veja LEIA-ME.md."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import traceback


def salvar_json(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def versao(pacote):
    try:
        return version(pacote)
    except PackageNotFoundError:
        return None


def argumentos():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Caminho do PDF de entrada")
    parser.add_argument("--saida", type=Path, default=Path(__file__).parent / "saida")
    parser.add_argument("--inicio", type=int, default=1, help="Primeira pagina fisica (1 = primeira)")
    parser.add_argument("--fim", type=int, help="Ultima pagina fisica, inclusive; omita para ir ao fim")
    parser.add_argument("--ocr", choices=["auto", "desligado", "forcado"], default="auto")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error("Informe um arquivo PDF existente.")
    if args.inicio < 1 or (args.fim is not None and args.fim < args.inicio):
        parser.error("Intervalo invalido: use 1 <= inicio <= fim.")
    if args.threads < 1:
        parser.error("threads deve ser positivo.")
    return args


def main():
    args = argumentos()
    pdf = args.pdf.resolve()
    # Uma pasta por execucao evita sobrescrever experimentos anteriores.
    identificador = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    pasta = args.saida.resolve() / f"{pdf.stem}_{identificador}"
    pasta.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(pasta / "execucao.log", encoding="utf-8"), logging.StreamHandler()],
    )
    inicio = perf_counter()
    relatorio = {
        "inicio_utc": datetime.now(timezone.utc).isoformat(),
        "arquivo": str(pdf),
        "tamanho_bytes": pdf.stat().st_size,
        "python": sys.version,
        "sistema": platform.platform(),
        "processador": platform.processor(),
        "cpus_logicas": os.cpu_count(),
        "versoes": {p: versao(p) for p in ["docling", "docling-core", "torch", "easyocr"]},
        "intervalo_solicitado": [args.inicio, args.fim],
        "ocr": args.ocr,
        "idiomas_ocr": ["pt", "en"],
        "dispositivo": "cpu",
        "threads": args.threads,
        "observacao": "Tempo inclui inicializacao; na primeira execucao pode incluir downloads. Nao mede acuracia nem pico de RAM.",
    }
    try:
        with pdf.open("rb") as arquivo:
            relatorio["sha256"] = hashlib.file_digest(arquivo, "sha256").hexdigest()

        # Os imports ficam aqui para --help funcionar mesmo antes da instalacao.
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions, TableFormerMode
        from docling.datamodel.settings import DEFAULT_PAGE_RANGE
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import ImageRefMode

        opcoes = PdfPipelineOptions()
        opcoes.enable_remote_services = False
        opcoes.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=args.threads)
        opcoes.do_ocr = args.ocr != "desligado"
        opcoes.ocr_options = EasyOcrOptions(
            lang=["pt", "en"], use_gpu=False, force_full_page_ocr=args.ocr == "forcado"
        )
        opcoes.do_table_structure = True
        opcoes.table_structure_options.mode = TableFormerMode.ACCURATE
        opcoes.generate_picture_images = True
        opcoes.images_scale = 2.0
        # A hierarquia de capitulos fica para um experimento posterior.
        salvar_json(pasta / "configuracao.json", opcoes.model_dump(mode="json"))
        conversor = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opcoes)},
        )

        logging.info("Convertendo %s. Saida: %s", pdf.name, pasta)
        inicio_conversao = perf_counter()
        resultado = conversor.convert(
            pdf,
            page_range=(args.inicio, args.fim if args.fim is not None else DEFAULT_PAGE_RANGE[1]),
            raises_on_error=False,
        )
        relatorio["segundos_conversao"] = perf_counter() - inicio_conversao
        relatorio["status_docling"] = resultado.status.value
        relatorio["erros_docling"] = [str(e) for e in resultado.errors]
        if resultado.status.value not in {"success", "partial_success"}:
            raise RuntimeError(f"Conversao sem sucesso: {resultado.status.value}")

        documento = resultado.document
        inicio_exportacao = perf_counter()
        imagens = pasta / "imagens"
        documento.save_as_json(pasta / "documento.json", artifacts_dir=imagens, image_mode=ImageRefMode.REFERENCED)
        documento.save_as_markdown(pasta / "documento.md", artifacts_dir=imagens, image_mode=ImageRefMode.REFERENCED)
        documento.save_as_html(pasta / "documento.html", artifacts_dir=imagens, image_mode=ImageRefMode.REFERENCED)

        # Resumo auxiliar de TODOS os itens de texto/tabela/figura, inclusive rodapes.
        # A ordem de leitura e as relacoes completas continuam no documento.json.
        elementos = []
        for item in [*documento.texts, *documento.tables, *documento.pictures]:
            elementos.append({
                "referencia": item.self_ref,
                "tipo": item.label.value,
                "texto": getattr(item, "text", None),
                "origens": [p.model_dump(mode="json") for p in item.prov],
            })
        salvar_json(pasta / "elementos.json", elementos)
        relatorio["segundos_exportacao"] = perf_counter() - inicio_exportacao
        relatorio["paginas_representadas"] = len(documento.pages)
        relatorio["contagem_por_tipo"] = dict(Counter(e["tipo"] for e in elementos))
        relatorio["segundos_conversao_por_pagina"] = (
            relatorio["segundos_conversao"] / len(documento.pages) if documento.pages else None
        )
        relatorio["conversao_completa"] = resultado.status.value == "success"
        if not relatorio["conversao_completa"]:
            logging.warning("Resultado PARCIAL: revise erros_docling antes de usar os arquivos.")
    except Exception as erro:
        relatorio["conversao_completa"] = False
        relatorio["excecao"] = str(erro)
        (pasta / "erro.txt").write_text(traceback.format_exc(), encoding="utf-8")
        logging.exception("Falha. Consulte erro.txt e relatorio.json em %s", pasta)
    finally:
        relatorio["segundos_ate_fim_processamento"] = perf_counter() - inicio
        # Snapshot do ambiente; isto nao fixa revisoes dos pesos dos modelos.
        ambiente = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if ambiente.returncode == 0:
            (pasta / "requirements-executados.txt").write_text(ambiente.stdout, encoding="utf-8")
        else:
            relatorio["aviso_snapshot"] = ambiente.stderr
        salvar_json(pasta / "relatorio.json", relatorio)
    print(f"\nArquivos desta execucao: {pasta}")
    return 0 if relatorio.get("conversao_completa") else 1


if __name__ == "__main__":
    sys.exit(main())
