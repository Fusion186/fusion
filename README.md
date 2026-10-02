# Projeto Fusion Jiu Jitsu

Aplicativo desktop em Python 3.10+ usando Tkinter e SQLite. O Pillow habilita o editor de foto com recorte, zoom e rotação, além do suporte a JPG, JPEG e WebP. Sem ele, o programa abre, mas o editor de fotos fica indisponível; PNG e GIF já salvos continuam visíveis.

## Executar

No Windows, clique duas vezes em `iniciar.bat`. Ou abra um terminal nesta pasta e execute:

```powershell
py -3 main.py
```

Para habilitar fotos JPG, JPEG e WebP, instale o suporte opcional:

```powershell
py -3 -m pip install -r requirements.txt
```

O banco `fusion_jiu_jitsu.db` será criado automaticamente ao lado do programa.

## Acesso inicial

| Perfil | Usuário | Senha |
|---|---|---|
| Professor | `professor` | `Fusion@2026` |
| Instrutor | `instrutor` | `Fusion@2026` |

As senhas são armazenadas como hashes no banco. Altere as credenciais antes de usar o sistema com dados reais. O professor pode gerenciar contas da equipe pela página **Equipe**, incluindo redefinição de senha; cada usuário também pode alterar a própria senha em **Configurações**. A senha mestre definida no código continua funcionando como acesso de recuperação.

## Funcionalidades

- Login administrativo para professor e instrutor.
- Opção para mostrar ou ocultar a senha digitada na tela de login.
- Acesso do aluno por código único, sem senha.
- Visão geral com totais de alunos, presenças do dia e dias de aula registrados.
- Total de aulas contabilizado manualmente, uma vez por data, pelos controles de adicionar/remover.
- Ranking geral rolável pela barra e pela roda do mouse, com destaque para os três primeiros colocados.
- Logo Fusion na tela de acesso e identidade visual em preto, vermelho e dourado.
- Cadastro de alunos com código único no formato `FUS-XXXXXX` e data de nascimento.
- Edição do nome, código, data de nascimento, faixa e telefone; códigos repetidos são recusados.
- Prévia individual da área do aluno pela lista administrativa.
- Foto de perfil opcional, escolhida e ajustada pelo próprio aluno com recorte, zoom e rotação; também visível na prévia administrativa.
- Histórico dos logins dos alunos na barra lateral e em uma página administrativa completa.
- Gerenciamento de contas da equipe pelo perfil Professor, com criação, edição, redefinição de senha e exclusão; o sistema protege a conta conectada e exige ao menos um professor.
- Aba de aniversariantes com seleção de mês e abertura automática no mês atual.
- Área do aluno somente para consulta: perfil, total de presenças, ranking e aniversariantes.
- Ordenação da chamada por nome, faixa ou quantidade de presenças no dia.
- Chamada com vários registros de aula por aluno no mesmo dia; é possível remover o último registro.
- Faixas adultas e progressões infantis reconhecidas no sistema IBJJF (faixa combinada com branca, sólida e combinada com preta).

O programa migra automaticamente bancos existentes para permitir mais de uma aula no mesmo dia, preservando as presenças registradas e usando as datas já existentes para iniciar o total de aulas.
# fusion
