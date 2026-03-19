# Proxmox Commissioner
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.md)
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.pt-br.md)

## O que e o Proxmox Commissioner?

Uma ferramenta com Terraform e Ansible para simplificar servicos rodando em maquinas virtuais no Proxmox Virtual Environment.

Ela e voltada para quem faz homelab ou equipes pequenas que usam PVE.

### O que ele faz?

1. Criar, configurar e proteger VMs
2. Enviar e fazer deploy de stacks Docker completas com suporte a armazenamento remoto via NFS
3. Enviar configuracoes e fazer deploy de Nginx com certificados DNS-01 do Cloudflare
4. Adicionar ou remover servicos mantendo a configuracao
5. Migrar VMs entre nos do cluster com praticidade

Ele provisiona Maquinas Virtuais em um cluster Proxmox e aplica configuracoes de seguranca e servico com Ansible. Cada **servico** (ex.: media stack, banco de dados, app web) tem seu proprio state do Terraform, diretorio de configuracao e ciclo de vida -- assim voce pode criar, proteger e configurar VMs de forma independente por servico.

### Como ele faz?

Basta criar um novo servico a partir do template, no diretorio raiz do projeto, e executar o script de deploy:

```bash
bash scripts/new-service-from-template.sh nome-do-servico
bash configs/services/nome-do-servico/deploy-service.sh
```
Isso cria uma VM com configuracao padrao:
- 1 vCPU
- 1 GB de RAM
- 16 GB de disco

A partir daqui, uma serie de playbooks e roles do Ansible pode:
- Adicionar usuario nao-root
- Melhorar a configuracao de segurança do SSH
- Instalar Docker e Docker Compose
- Instalar, configurar e fazer deploy do Nginx
- Configurar compartilhamentos NFS
- Copiar arquivos de configuracao
- Fazer deploy de stacks Docker

Leia o [Guia de configuração](docs/setup-guide.pt-br.md) e o [Guia do Usuário](docs/user-guide.pt-br.md) antes de começar.

### Estrutura do projeto

```
config/
  defaults/
    terraform/
      infrastructure.env              # Defaults compartilhados Terraform + Proxmox (gitignored)
      infrastructure.env.example      # Exemplo para infrastructure.env
    local.env.example                 # Template para local.env
    local.env                         # Arquivo de config do Ansible/senha do vault (gitignored)
    ansible/
      base.yml                        # Variaveis Ansible nao sensiveis
      vault.yml.example               # Exemplo de arquivo de vault (criptografe isso)
      vault.yml                       # Segredos criptografados do vault usados pelos playbooks
    services/
      service-template/
        service-template.infrastructure.env.example  # Template para overrides por servico
  services/
    <servico>/
      <servico>.infrastructure.env    # Especificacoes da VM e overrides por servico
      terraform/                      # Root Terraform por servico (state + outputs)
      filesystem/                     # Payload de arquivos do servico enviado para a VM
      ansible/
        <servico>.inventory.yml       # Inventario auto-gerado para essa VM

terraform/
  modules/
    proxmox-vm/                       # Modulo compartilhado de VM (resources, variables, outputs)
    proxmox-lxc/

ansible/
  playbooks/                          # Seguranca, Docker, Nginx etc.
  roles/                              # Roles Ansible reutilizaveis

scripts/
  service-commission.sh               # Terraform apply + info da VM (e qm migrate opcional)
  service-migrate.sh                  # Terraform state + qm migrate da VM existente para outro no Proxmox
  service-decommission.sh             # Terraform destroy
  new-service-from-template.sh        # Cria `config/services/<servico>/` a partir de `config/defaults/services/service-template/`
  inventories-regenerate-all.sh       # Gera inventario para todos os servicos
  inventory-generate.sh               # Gera inventario para um servico
  secure-vm.sh                        # Executa playbooks de seguranca em uma VM de servico
  install-docker.sh                   # Instala Docker em uma VM de servico
  install-nginx.sh                    # Instala Nginx em uma VM de servico
  mount-nfs.sh                        # Configura montagens NFS em uma VM de servico
  service-push.sh                     # Envia arquivos + deploy opcional do docker compose
  lib/common.sh                       # Helpers compartilhados
```
