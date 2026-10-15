# Guia do usuario

Este arquivo fornece instrucoes para o usuario e documenta fluxos de trabalho para referencia.
Use `chmod +x` nos arquivos de script se quiser evitar invocar `bash`.

## Servicos

Servicos sao a principal abstracao do Proxmox Commissioner.
Eles estao vinculados a uma unica VM.

Aqui esta a estrutura base:

```
  services/
    <service>/
      <service>.infrastructure.env    # Especificacoes e sobrescritas de VM por servico
      deploy.conf                     # Quais playbooks este servico executa, por fase
      deploy-service.sh               # Entrypoint de deploy deste servico
      terraform/                      # Raiz Terraform por servico (state + outputs)
      filetree/                       # Payload de arquivos do servico implantado na VM
      ansible/
        <service>.inventory.yml       # Inventario auto-gerado para esta VM
```

Servicos permitem que os scripts executem, mantenham o estado do Terraform e a configuracao de cada VM.
Embora servicos com varias VMs nao sejam suportados, tenho usado o padrao `service-role` para agrupa-los.

Arquivos em `service/filetree` devem replicar os caminhos absolutos desejados e serao enviados para a VM.
Conteudo em diretorios `/home/*` e tratado de forma diferente para manter permissao de usuario. Outros locais sao copiados com propriedade `root`.

### Configurando um servico

Servicos sao gerados a partir do template em `config/defaults/service/service-template`. Use o script auxiliar:

```bash
bash scripts/new-service-from-template.sh your-service-name
```

Isso adiciona a arvore de arquivos base, o `deploy.conf` e o script de deploy, alem de `your-service-name.infrastructure.env` e os arquivos Terraform obrigatorios.

Configure o arquivo de infraestrutura com a configuracao de hardware desejada, liste os playbooks desejados em `deploy.conf` e execute o script de deploy; sua VM estara pronta em breve.

```bash
bash config/services/your-service-name/deploy-service.sh --commission
```

### Fluxo completo

Use `scripts/new-service-from-template.sh <service>` para criar `config/services/<service>/` a partir de `config/defaults/services/service-template/`, depois personalize o env por servico.

```bash
# 1. Crie o diretorio do servico a partir do template
bash scripts/new-service-from-template.sh myservice

# 2. Edite o env de infraestrutura por servico (especificacoes da VM + sobrescritas)
nano config/services/myservice/myservice.infrastructure.env

# 3. Escolha os playbooks que este servico deve executar
nano config/services/myservice/deploy.conf

# 4. Provisione a VM e configure-a de ponta a ponta
bash scripts/service-deploy.sh myservice --commission

# 5. Execute novamente quando quiser reconvergir (o hardening e pulado automaticamente)
bash scripts/service-deploy.sh myservice

# 6. Exclua a VM
bash scripts/service-decommission.sh myservice
```

### Deploy e redeploy

`service-deploy.sh` e a forma normal de executar um servico. Ele sonda a VM por SSH antes de qualquer coisa, entao sabe se o hardening inicial ja aconteceu e nunca tenta reexecutar uma etapa que nao consegue mais conectar:

| O que a sondagem encontra | O que executa |
|---------------------------|---------------|
| `devops` acessivel na porta SSH endurecida | Apenas os playbooks de convergencia |
| `devops` acessivel na porta 22 | Termina o hardening, depois converge |
| Porta 22 aberta, mas sem chave `devops` | Bootstrap completo, depois converge |
| Nada responde | Nada; avisa que a VM esta inacessivel |

Isso significa que reexecutar o mesmo comando e seguro, e nao ha necessidade de comentar etapas manualmente.

As listas de playbooks vem do `deploy.conf` do servico:

```bash
# Executa uma vez em uma VM nova. Pulado automaticamente quando a VM ja esta endurecida.
BOOTSTRAP_PLAYBOOKS=(
    00-initial.yml
    10-base-security.yml
)

# Idempotente, executa em todo deploy.
CONVERGE_PLAYBOOKS=(
    25-file-push.yml
    20-docker.yml
    26-docker-deploy.yml
)

# Imperativo ou nao idempotente. Executa apenas com --post-deploy.
POSTDEPLOY_PLAYBOOKS=(
    27-post-deploy.yml
)
```

Flags uteis:

```bash
# Veja o que seria executado, sem executar
bash scripts/service-deploy.sh myservice --dry-run

# Provisione a VM e gere o inventario primeiro
bash scripts/service-deploy.sh myservice --commission

# Execute tambem o post-deploy.sh na VM
bash scripts/service-deploy.sh myservice --post-deploy

# Execute um unico playbook e pare
bash scripts/service-deploy.sh myservice --only 23-node-exporter.yml

# Sobrescreva a sondagem quando voce ja sabe o estado
bash scripts/service-deploy.sh myservice --bootstrap
bash scripts/service-deploy.sh myservice --converge
```

A regeneracao do inventario e opcional, via `--refresh-inventory` (ou implicita em `--commission`), porque `inventory-generate.sh` reescreve o arquivo do zero e descarta variaveis de host editadas a mao, como `nfs_mountpoints`.

Se um playbook falhar, a execucao para e imprime o comando exato para retomar daquele ponto.

## Configuracao

Toda a configuracao e gerenciada por variaveis de ambiente em `config/`.
A configuracao possui ordem de carregamento em camadas; valores do ultimo arquivo substituem valores do primeiro.

1. `local.env` - Configuracao do Ansible e de outros componentes de ambiente
2. `terraform/infrastructure.env` - Defaults de Terraform/Proxmox
3. `config/services/<service>/<service>.infrastructure.env` - Sobrescritas por servico

### Visao geral

#### Nivel de defaults

- **`config/defaults/terraform/infrastructure.env`**
  - Defaults compartilhados de Terraform + autenticacao do Proxmox
  - (ignorado no git; crie a partir de `config/defaults/terraform/infrastructure.env.example`)

- **`config/defaults/local.env`**
  - Configuracao do Ansible e outras configuracoes adicionais de ambiente
  - (ignorado no git; crie a partir de `config/defaults/local.env.example`)

#### Nivel de servico

- **`config/services/<service>/<service>.infrastructure.env`**
  - Especificacoes de VM por servico e sobrescritas de Terraform
  - **Altere as especificacoes da VM (vCPU, RAM, HDD) aqui!**
  - (ignorado no git; gerado a partir de `config/defaults/services/service-template/`)

## Scripts utilitarios

Scripts utilitarios em `scripts/` permitem acesso direto as funcionalidades e podem ser chamados por scripts de deploy de servicos. Todo script recebe um **nome de servico** como primeiro argumento.

### Funcionalidades atuais:

- Criar um novo esqueleto de servico a partir do template.
```bash
bash scripts/new-service-from-template.sh service-name
```

- Fazer deploy de um servico, executando apenas as fases que ainda faltam.
```bash
bash scripts/service-deploy.sh service-name
bash scripts/service-deploy.sh service-name --help
```

- Criar uma nova VM para um servico.
```bash
bash scripts/service-commission.sh service-name
```

- Fazer decommission (destruir) da VM de um servico.
```bash
bash scripts/service-decommission.sh service-name
```

- Migrar uma VM para outro no Proxmox.
```bash
bash scripts/service-migrate.sh service-name destination-node destination-node-ip
```

- Enviar o payload `filetree` do servico para a VM.
```bash
bash scripts/run-playbook.sh service-name 25-file-push.yml
```

- Fazer deploy da stack Docker Compose do servico.
```bash
bash scripts/run-playbook.sh service-name 26-docker-deploy.yml
```

- Gerar ou atualizar um inventario de servico a partir dos outputs do Terraform.
```bash
bash scripts/inventory-generate.sh service-name
```

- Regenerar inventarios para todos os servicos (ou para um servico unico).
```bash
bash scripts/inventories-regenerate-all.sh
```

- Executar um playbook especifico do Ansible em uma VM de servico.
```bash
bash scripts/run-playbook.sh service-name 15-web-server.yml
```

## Configuracoes padrao

### Configuracao Terraform padrao e especificacoes de VM

```bash
# 1. Copie os defaults compartilhados de Terraform/Proxmox
cp config/defaults/terraform/infrastructure.env.example config/defaults/terraform/infrastructure.env

# 1. Edite os defaults de Terraform/Proxmox (tokens, senhas, configuracoes de clone/storage/network)
nano config/defaults/terraform/infrastructure.env
```

### Configuracao Ansible padrao e cofre de segredos
```bash
# 1. Copie o template de configuracao do Ansible (local.env)
cp config/defaults/local.env.example config/defaults/local.env
```

### Estrutura de variaveis
- `config/defaults/ansible/base.yml`: Variaveis comuns do Ansible nao sensiveis
- `config/defaults/ansible/vault.yml`: Variaveis sensiveis criptografadas (usadas via Ansible vault)
- `config/services/<service>/ansible/inventory/<service>.deployment.yml`: Inventario por servico auto-gerado a partir dos outputs do Terraform

### Configure seu Ansible vault

```bash
# 1. (Se necessario) Crie vault.yml a partir do exemplo e criptografe-o
cp config/defaults/ansible/vault.yml.example config/defaults/ansible/vault.yml
ansible-vault encrypt config/defaults/ansible/vault.yml

# 2. Edite o vault (tambem funciona para arquivos ja criptografados)
ansible-vault edit config/defaults/ansible/vault.yml
```

## Cluster: direcionando para nos Proxmox diferentes

A VM e clonada no Proxmox de "origem" (`TF_VAR_proxmox_node` / `TF_VAR_proxmox_node_ip` de `config/defaults/terraform/infrastructure.env`).

Para mover a VM para outro no apos o provisionamento, defina `TF_VAR_proxmox_destination_node` e `TF_VAR_proxmox_destination_node_ip` no `*.infrastructure.env` do servico.
