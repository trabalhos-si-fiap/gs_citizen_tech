# 📢 Reclame Já

## Global Solution 2026 | FIAP - Citizen Tech

O **Reclame Já** é uma plataforma de participação cidadã desenvolvida para a **Global Solution Citizen Tech da FIAP**.

A solução tem como objetivo conectar cidadãos, órgãos públicos e concessionárias por meio de um canal único para registro, encaminhamento e acompanhamento de problemas urbanos, promovendo mais transparência, eficiência e participação social.

Por meio de Inteligência Artificial, geolocalização e um modelo de decisão baseado em regras, o sistema classifica automaticamente as ocorrências, identifica os responsáveis e permite que o cidadão acompanhe todo o processo até sua conclusão.

---

# 👨‍💻 Equipe

Projeto desenvolvido pelos alunos do **3º ano de Sistemas de Informação (3SIOA)** da FIAP:

- Elias
- Juliana
- Marcella
- Murilo

---

# 🎯 Desafio Proposto

O desafio **Citizen Tech** busca incentivar a criação de soluções tecnológicas capazes de melhorar a relação entre cidadãos e serviços públicos, promovendo cidades mais inteligentes, sustentáveis e inclusivas.

O **Reclame Já** foi criado para solucionar um problema recorrente da população: a dificuldade em identificar o órgão responsável por problemas urbanos e acompanhar o andamento das solicitações realizadas.

---

# 🚨 Problema

Os cidadãos enfrentam diariamente diversos problemas urbanos, entre eles:

- Falhas no transporte público;
- Falta de medicamentos ou profissionais em unidades de saúde;
- Problemas de saneamento básico;
- Árvores com risco de queda;
- Iluminação pública defeituosa;
- Buracos e falhas na infraestrutura urbana;
- Riscos à segurança em espaços públicos.

Atualmente, essas ocorrências são registradas por diferentes canais, muitas vezes sem transparência, rastreabilidade ou retorno efetivo ao cidadão.

---

# 💡 Solução Proposta

O **Reclame Já** centraliza toda a comunicação entre cidadãos e prestadores de serviços públicos, permitindo:

- Registro rápido de ocorrências;
- Upload de fotos;
- Geolocalização automática;
- Classificação inteligente da ocorrência;
- Encaminhamento automático para o órgão responsável;
- Acompanhamento do status da solicitação;
- Agrupamento de ocorrências semelhantes;
- Geração de indicadores e dashboards para gestão pública.


---

# 🌎 Objetivos de Desenvolvimento Sustentável (ODS)

O projeto contribui diretamente para os seguintes ODS da ONU:

- ODS 11 – Cidades e Comunidades Sustentáveis
- ODS 3 – Saúde e Bem-Estar
- ODS 9 – Indústria, Inovação e Infraestrutura
- ODS 10 – Redução das Desigualdades

---

# 🚀 Funcionalidades

## Para o Cidadão

- Cadastro e autenticação;
- Registro de ocorrências;
- Consulta de protocolos;
- Notificações de atualização;
- Feed Local para interação;
- Histórico de solicitações.

## Para Gestores Públicos

- Dashboard gerencial;
- Mapa de calor de ocorrências;
- Indicadores de desempenho;
- Monitoramento por categoria;
- Priorização baseada em dados;
- Relatórios gerenciais.

---

# 🏗️ Arquitetura da Solução

## Stack Tecnológica

| Camada | Tecnologia |
|----------|------------|
| Mobile | Flutter |
| Frontend Web | Angular |
| Backend | Python + FastAPI |
| IA Generativa | Ollama LLM |
| Motor de Decisão | Matriz de Responsabilidade |
| APIs | REST |
| Documentação | Swagger/OpenAPI |

---

## Mobile

### Tecnologia
Flutter

### Responsabilidades

- Interface do cidadão;
- Registro de ocorrências;
- Upload de imagens;
- Acompanhamento de protocolos;
- Notificações.

### Benefícios

- Aplicação multiplataforma;
- Código único para Android e iOS;
- Fácil manutenção;
- Alto desempenho.

---

## Frontend Web

### Tecnologia
Angular

### Responsabilidades

- Dashboard administrativo;
- Gestão de ocorrências;
- Visualização de indicadores;
- Relatórios gerenciais;
- Monitoramento operacional.

### Benefícios

- Arquitetura SPA (Single Page Application);
- Componentização;
- Escalabilidade;
- Melhor experiência do usuário.

---

## Backend

### Tecnologia
Python + FastAPI

### Responsabilidades

- APIs REST;
- Autenticação e autorização;
- Processamento das ocorrências;
- Integração com IA;
- Regras de negócio;
- Integrações futuras com sistemas públicos.

### Benefícios

- Alta performance;
- Documentação automática;
- Facilidade de integração;
- Arquitetura moderna e escalável.

---

## Inteligência Artificial

### Ollama LLM

A plataforma utiliza um modelo de linguagem disponibilizado pela **Ollama** para auxiliar na interpretação dos relatos enviados pelos usuários.

### Funções da IA

- Classificação da ocorrência;
- Identificação da categoria;
- Análise do contexto do relato;
- Apoio à priorização da demanda.

---

## Modelo de Decisão

Após a classificação realizada pelo LLM, uma **Matriz de Responsabilidade** é utilizada para determinar:

- Nível de criticidade;
- Categoria da ocorrência;
- Órgão responsável;
- Fluxo de encaminhamento.

Essa abordagem garante maior transparência, previsibilidade e auditabilidade das decisões tomadas pelo sistema.

---

---

# 📂 Estrutura do Projeto

```text
reclame-ja/
│
├── docs/
│   ├── Documentação Final (PDF)
│   ├── Apresentação Técnica
│   ├── Pitch Comercial
│   ├── MER
│   ├── DER
│   └── Scripts PL/SQL
│
├── docs_tecnicas/
│   ├── Backend
│   ├── Mobile
│   ├── Web
│   └── BPMN
│
├── backend/
│   ├── API FastAPI
│   ├── Integração IA
│   └── Regras de Negócio
│
├── mobile/
│   └── Aplicação Flutter
│
└── web/
    └── Aplicação Angular
```

---

# ⚙️ Pré-requisitos, Instalação e Execução


## 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/reclame-ja.git

cd reclame-ja
```

---



# 🔄 Fluxo da Solução

```text
Cidadão
    ↓
Aplicativo Flutter
    ↓
API FastAPI
    ↓
LLM (Ollama)
    ↓
Classificação da Ocorrência
    ↓
Matriz de Responsabilidade
    ↓
Identificação do Órgão Responsável
    ↓
Registro e Encaminhamento
    ↓
Dashboard Angular
    ↓
Monitoramento e Indicadores
```

---

# 📊 Impacto Esperado

## Para os cidadãos

- Canal único para reportar problemas;
- Maior transparência;
- Acompanhamento das solicitações;
- Participação ativa na melhoria da cidade.

## Para os gestores públicos

- Visão consolidada das demandas;
- Priorização baseada em dados;
- Redução do tempo de resposta;
- Melhor alocação de recursos públicos.

---

# 📈 Evoluções Futuras

## V1 - Expansão para novas cidades

- Registro de ocorrências;
- Classificação automática;
- Acompanhamento em tempo real.

## V2 - Inteligência Coletiva

- Agrupamento de ocorrências semelhantes;
- Priorização colaborativa;
- Confirmação por moradores.

## V3 - Integrações Oficiais

- Prefeituras;
- Ouvidorias;
- Concessionárias;
- Sistemas públicos.

## V4 - Inteligência Preditiva

- Previsão de problemas urbanos;
- Identificação de riscos;
- Apoio ao planejamento público.

---
