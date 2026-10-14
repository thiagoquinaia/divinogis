# Diretrizes de Contribuição (Contributing to DivinoGIS)

Primeiramente, obrigado pelo interesse em contribuir com o **DivinoGIS**! Projetos de código aberto crescem e se tornam melhores graças à colaboração de pessoas como você.

---

## 🧭 Como Você Pode Contribuir?

Você não precisa ser um especialista em SIG ou Python para colaborar. Aceitamos com entusiasmo contribuições de diversos tipos:

- 🐛 **Reportar Erros (Bugs)**: Encontrou um problema ou comportamento inesperado? Abra uma Issue detalhada.
- 💡 **Sugerir Funcionalidades**: Tem ideias para novas ferramentas, novos basemaps, outros formatos vetoriais ou opções de visualização? Compartilhe conosco!
- 📝 **Melhorar a Documentação**: Correções de texto, exemplos práticos, novos tutoriais e traduções.
- 💻 **Contribuir com Código**: Implementação de novas funcionalidades, refatorações, testes e otimizações de performance.

---

## 🛠️ Configuração do Ambiente de Desenvolvimento

### 1. Faça um Fork e Clone o Repositório
```bash
# Clone o seu fork (substitua pelo seu usuário)
git clone https://github.com/SEU_USUARIO/divinogis.git
cd divinogis
```

### 2. Crie uma Branch para a sua Modificação
```bash
git checkout -b feature/minha-nova-funcionalidade
# ou para correção de bug:
git checkout -b fix/correcao-do-problema
```

### 3. Crie e Ative um Ambiente Virtual Python
```bash
python3 -m venv venv

# Linux / macOS:
source venv/bin/activate

# Windows:
.\venv\Scripts\Activate.ps1
```

### 4. Instale as Dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Execute a Aplicação
```bash
python3 app.py
```
Acesse no navegador: `http://localhost:5001`.

---

## 📋 Padrões de Código

Para mantermos o projeto limpo, legível e de fácil manutenção:

- **Python**: Siga as diretrizes da [PEP 8](https://peps.python.org/pep-0008/). Escreva código limpo com nomes descritivos para variáveis e funções.
- **JavaScript**: Utilize sintaxe moderna ES6+, mantenha o código modular e com comentários explicativos em seções complexas.
- **Commits Semânticos**: Recomendamos mensagens de commit claras e objetivas, de preferência no formato:
  - `feat: adiciona suporte à malha de microrregiões do IBGE`
  - `fix: corrige cálculo de escala no exportador STL`
  - `docs: atualiza instruções de instalação no README`
  - `refactor: simplifica método de reprojeção geodésica`

---

## 🚀 Enviando um Pull Request (PR)

1. Certifique-se de que o código roda sem erros localmente.
2. Faça o commit das suas alterações:
   ```bash
   git add .
   git commit -m "feat: descrição objetiva da funcionalidade"
   ```
3. Envie para o seu fork no GitHub:
   ```bash
   git push origin feature/minha-nova-funcionalidade
   ```
4. Abra um **Pull Request** para a branch `main` do repositório original.
5. Descreva de forma clara as mudanças realizadas e o motivo da proposta.

Agradecemos imensamente pela sua colaboração com o DivinoGIS! 🗺️✨
