# Primeiro experimento: PDF de TCC para documento estruturado

Este roteiro foi preparado para Windows e PowerShell. O programa usa Docling com CPU, reconhecimento de tabelas e EasyOCR em português e inglês. Não exige chave de API. Os modelos são baixados na primeira utilização; o processamento configurado é local.

Os arquivos do experimento já estão criados. A instalação das dependências e a conversão de um TCC ainda precisam ser executadas por você. A sintaxe do script foi verificada; isso não equivale a uma conversão validada.

## 1. Instalar Python

Se você já possui Python 3.12, execute `py -3.12 --version` e avance se aparecer Python 3.12.x.

Caso contrário, acesse https://www.python.org/downloads/windows/ e instale o Python install manager oficial. Feche e abra o PowerShell depois da instalação. Execute:

```powershell
py install 3.12
py -3.12 --version
```

O primeiro comando instala a versão escolhida; o segundo confirma a instalação. A versão 3.12 é uma escolha conservadora para este experimento, não a única versão suportada pelo Docling.

Se `py install` for interpretado como o nome de um arquivo, o comando `py` provavelmente aponta para o launcher antigo. Após instalar o manager, tente `pymanager install 3.12`. Se `py` não existir, reabra o terminal e verifique a instalação antes de seguir.

## 2. Entrar na pasta

Abra PowerShell pelo menu Iniciar. Execute uma etapa de cada vez e só avance quando ela terminar sem erro:

```powershell
Set-Location 'C:\Users\matheusalves\Desktop\TCC\experimento_docling'
Get-ChildItem
```

Você deve encontrar converter.py, requirements.txt, LEIA-ME.md e a pasta entrada. O comando Set-Location muda a pasta de trabalho; todos os caminhos relativos dos próximos comandos partem dela. No PowerShell, `.` significa a pasta atual.

## 3. Criar um ambiente virtual

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
```

O ambiente virtual é uma instalação isolada das bibliotecas deste projeto. Ele fica em .venv. Usaremos diretamente seu python.exe, por isso não precisamos executar Activate.ps1 nem alterar a política de execução do Windows.

## 4. Instalar as bibliotecas

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "from docling.document_converter import DocumentConverter; from importlib.metadata import version; print('Docling:', version('docling'))"
```

pip instala pacotes Python. `-r requirements.txt` manda ler a lista do projeto. O extra [easyocr] instala o mecanismo de OCR que o script escolhe explicitamente. PyTorch e outras dependências também serão instalados. Aguarde o retorno do prompt; essa etapa pode baixar arquivos grandes. Reserve alguns GB livres para ambiente, modelos e resultados, sem tratar isso como requisito mínimo garantido.

O comando de importação deve imprimir a versão instalada. `pip check` deve informar que não há dependências quebradas.

Registre as versões resolvidas:

```powershell
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements-lock.txt
```

O requirements.txt aceita versões 2.x a partir de 2.70. Isso facilita a instalação inicial, mas não fixa uma versão exata. requirements-lock.txt registra o conjunto efetivamente instalado. Em outro ambiente com Python e sistema compatíveis, instale usando `-r requirements-lock.txt`. Não atualize bibliotecas entre as medições. Cada execução também grava sua própria lista de pacotes. Pesos dos modelos têm cache separado; para reprodução rigorosa futura, será necessário preservar suas revisões/arquivos também.

## 5. Adicionar um TCC

Pelo Explorador de Arquivos, copie um PDF para a pasta entrada e nomeie a cópia tcc_exemplo.pdf. Preserve o arquivo original. O roteiro usa esse nome como convenção; nenhum TCC foi baixado ou criado.

```powershell
Test-Path '.\entrada\tcc_exemplo.pdf'
```

O resultado deve ser True. Um PDF digital com texto selecionável é um bom primeiro caso; documentos escaneados também podem ser processados com OCR. Confira se a extensão não ficou .pdf.pdf.

## 6. Entender o programa antes de executar

Leia converter.py no editor de sua preferência. Ele realiza estas operações:

1. Recebe o caminho do PDF e valida argumentos.
2. Cria uma pasta exclusiva para esta execução.
3. Configura CPU com quatro threads, OCR pt/en e reconhecimento de tabelas no modo ACCURATE.
4. Converte o intervalo solicitado em DoclingDocument, a representação estruturada do Docling.
5. Exporta JSON, Markdown, HTML e imagens das figuras detectadas.
6. Grava configuração, contagens, tempos, versões e eventuais erros.

O hash SHA-256 identifica o conteúdo do PDF, permitindo confirmar se dois testes usaram exatamente o mesmo arquivo. A função perf_counter mede tempo decorrido. Os imports do Docling são feitos dentro de main para que `--help` funcione mesmo antes de instalar dependências.

```powershell
.\.venv\Scripts\python.exe .\converter.py --help
```

OCR auto significa que o mecanismo está habilitado sem forçar a leitura integral de todas as páginas: o pipeline seleciona regiões conforme suas regras. Isso não garante detecção perfeita de toda região que precisa de OCR. O modo forcado pede OCR de página inteira; desligado usa o texto digital sem OCR.

## 7. Fazer uma conversão pequena

```powershell
.\.venv\Scripts\python.exe .\converter.py '.\entrada\tcc_exemplo.pdf' --inicio 1 --fim 5
```

Use esse intervalo se o documento tiver pelo menos cinco páginas; caso contrário, reduza --fim. Os números são posições físicas no arquivo, começando em 1, independentemente da numeração impressa.

Na primeira execução, downloads e carregamento dos modelos podem dominar o tempo. Mensagens sobre CPU são esperadas. Não interprete o tempo desse primeiro teste como velocidade de conversão estabilizada. Ao terminar, o programa imprime a pasta criada. Se ocorrer erro, consulte erro.txt, execucao.log e relatorio.json nessa pasta.

O teste inicial verifica o ambiente; as primeiras páginas de um TCC geralmente não bastam para avaliar tabelas, figuras ou texto do desenvolvimento.

## 8. Inspecionar as saídas

```powershell
$ultimaExecucao = Get-ChildItem '.\saida' -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Invoke-Item (Join-Path $ultimaExecucao.FullName 'documento.html')
Get-Content (Join-Path $ultimaExecucao.FullName 'relatorio.json') -Raw -Encoding utf8
```

Use os comandos depois de uma execução bem-sucedida. O primeiro seleciona a pasta mais recente; o segundo abre o HTML no navegador; o terceiro mostra o relatório.

| Arquivo | Finalidade |
|---|---|
| documento.json | Representação estruturada completa exportada pelo Docling; base para processamento futuro |
| documento.md | Conteúdo em Markdown, fácil de ler e comparar |
| documento.html | Visualização do conteúdo convertido no navegador; não reproduz a diagramação original |
| imagens/ | Imagens referenciadas nos arquivos, quando há figuras detectadas |
| elementos.json | Resumo de textos, tabelas e figuras com tipo, referência e proveniência |
| configuracao.json | Configuração completa do pipeline usado |
| relatorio.json | Status, erros, tempos, contagens e informações do ambiente |
| requirements-executados.txt | Versões dos pacotes presentes naquela execução |
| execucao.log | Mensagens de processamento |
| erro.txt | Detalhes de uma exceção, se ela ocorrer |

Mantenha os arquivos e a pasta de imagens juntos. Não mova somente o HTML se quiser que as figuras continuem aparecendo.

No documento.json, procure texts, tables, pictures, body e furniture. As relações de referência organizam os elementos; prov registra origem, incluindo page_no e bbox quando disponíveis. bbox é o retângulo do elemento; respeite seu coord_origin ao desenhá-lo sobre uma página. self_ref é o identificador/referência do item dentro desse documento.

elementos.json agrupa itens por coleção e NÃO representa a ordem de leitura. Para isso use as relações de documento.json ou a API iterate_items(). Markdown/HTML podem omitir camadas auxiliares como cabeçalhos e rodapés; use o JSON para auditar o documento completo.

Identificar section_header não significa recuperar toda a hierarquia de capítulos. A configuração inicial não habilita a recuperação adicional de níveis de títulos. Da mesma forma, extrair a imagem de um diagrama não significa compreender suas classes e relações.

## 9. Converter o TCC completo

```powershell
.\.venv\Scripts\python.exe .\converter.py '.\entrada\tcc_exemplo.pdf'
```

Sem --fim, o programa segue até o fim do documento. Cada execução cria uma nova pasta, sem sobrescrever resultados anteriores. relatorio.json deve indicar status_docling igual a success e conversao_completa igual a true. Status parcial significa que os arquivos não devem ser tratados como conversão completa.

## 10. Avaliar qualidade e desempenho separadamente

Para qualidade, compare PDF e saída lado a lado. Selecione uma página de texto, uma com títulos/subtítulos, uma tabela de requisitos, uma figura com legenda e uma página de referências. Inclua código se existir no TCC.

Registre página, elemento esperado, resultado observado e erro. Exemplos: título classificado como parágrafo; duas colunas da tabela misturadas; legenda separada da figura; caractere de código alterado. Ter muitos elementos detectados não prova acurácia. Success indica término técnico, não correção do conteúdo.

Para tempo, faça primeiro uma execução completa de preparação. Depois execute três vezes o MESMO comando completo e compare a mediana de segundos_conversao. Mantenha PDF, OCR, threads e versões iguais. Feche tarefas pesadas concorrentes. Cada comando abre um novo processo: mesmo com modelos baixados, a medição inclui carregamento/inicialização dentro de convert(). Não é uma medição de um serviço já aquecido em memória.

segundos_exportacao mede a escrita das representações e imagens; segundos_ate_fim_processamento inclui imports e preparação, mas exclui o snapshot final do pip e a escrita final do relatório. segundos_conversao_por_pagina é uma média, não uma medição individual das páginas. O programa não mede pico de memória.

## 11. Experimentos posteriores, uma variável por vez

Sem OCR:

```powershell
.\.venv\Scripts\python.exe .\converter.py '.\entrada\tcc_exemplo.pdf' --ocr desligado
```

OCR integral, apenas para investigar páginas problemáticas:

```powershell
.\.venv\Scripts\python.exe .\converter.py '.\entrada\tcc_exemplo.pdf' --inicio 10 --fim 12 --ocr forcado
```

Esses números são exemplos; escolha páginas existentes. Compare o mesmo intervalo também em modo auto. Não compare diretamente o tempo de três páginas com o documento inteiro. Desligar OCR pode perder palavras em figuras mesmo quando o corpo do PDF é digital.

## Problemas comuns

| Sintoma | Próximo passo |
|---|---|
| No module named docling | Confira se instalação e execução usam .venv\Scripts\python.exe |
| PDF não encontrado | Verifique pasta atual, extensão e caminho entre aspas |
| Erro ao baixar modelos | Leia o endereço e o erro no log; verifique conexão/proxy institucional e tente novamente quando a conexão funcionar |
| ImportError ou DLL load failed | Confira Python 64 bits e copie o erro completo; não instale pacotes aleatórios nem troque versões sem registrar |
| Execução muito lenta | Aguarde downloads iniciais e teste poucas páginas; não há duração garantida sem medir seu computador |
| Falta de memória | Diminua o intervalo de páginas; não trate execuções por partes como medição equivalente ao documento completo |
| Resultado vazio | Confira se o PDF abre normalmente e teste OCR em uma página escaneada |
| Títulos todos no mesmo nível | Identificação de títulos e hierarquia são problemas distintos; avaliaremos a reconstrução depois |

## Fontes oficiais

- Python no Windows: https://docs.python.org/3/using/windows.html
- Instalação e extras do Docling: https://docling-project.github.io/docling/getting_started/installation/
- Configuração de conversão: https://docling-project.github.io/docling/_generated/examples/custom_convert/
- Exportação de imagens: https://docling-project.github.io/docling/_generated/examples/export_figures/
- Configuração de CPU: https://docling-project.github.io/docling/_generated/examples/run_with_accelerator/
- Modelo de documento: https://docling-project.github.io/docling/concepts/docling_document/
- Downloads e opções avançadas: https://docling-project.github.io/docling/usage/advanced_options/

Roteiro elaborado em 23/09/2026. O primeiro teste real no seu ambiente deve confirmar compatibilidade das dependências e qualidade do resultado.
