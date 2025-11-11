# 🦑 Squid Proxy Monitor

**Squid Proxy Monitor** é uma aplicação em **Python + Streamlit** que realiza o **monitoramento em tempo real dos acessos do Squid Proxy**.  
O sistema lê o arquivo `access.log`, resolve os IPs dos clientes via DNS (com cache persistente), armazena as informações em banco SQLite e apresenta relatórios interativos com gráficos e estatísticas.

---

## 🚀 Funcionalidades

- 📡 **Monitoramento em tempo real** do arquivo de log do Squid (`/var/log/squid/access.log`);
- 🧠 **Cache DNS persistente** em banco SQLite (evita consultas repetidas);
- 💾 **Armazenamento permanente** de todos os acessos (tabela `access_log`);
- 🍕 **Gráfico de pizza** com os **Top 50 sites mais acessados**;
- 📈 **Gráfico de barras** com o **tráfego total por cliente (bytes)**;
- 🔄 Atualização automática e interface web interativa via Streamlit.

---

## 🧰 Tecnologias utilizadas

| Componente | Descrição |
|-------------|------------|
| **Python 3.9+** | Linguagem principal |
| **Streamlit** | Interface web em tempo real |
| **SQLite** | Banco de dados local persistente |
| **Plotly Express** | Gráficos interativos (pizza e barras) |
| **threading** | Monitoramento contínuo do log |
| **socket / DNS** | Resolução de IPs para hostnames |

---

## 🏗️ Estrutura do projeto


---

## ⚙️ Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/squid-monitor.git
cd squid-monitor

