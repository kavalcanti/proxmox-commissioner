# Proxmox Commissioner

[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.md)
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.pt-br.md)

## O que é o Proxmox Commissioner?

Uma pequena CLI, `pvc`, que transforma um manifesto YAML em serviços rodando no Proxmox Virtual Environment. O Terraform cria as VMs, o Ansible as configura e o `pvc` liga os dois.

Ele é voltado para quem faz homelab e equipes pequenas que usam PVE.

### O que ele faz?

1. Cria uma ou mais VMs por serviço (um banco de dados e um host de aplicação, por exemplo) a partir de um único arquivo
2. Sobe toda VM já protegida: SSH somente com chave em porta customizada, root bloqueado, firewall e fail2ban ativos
3. Instala Docker, nginx com certificados DNS-01 do Cloudflare, montagens NFS, Node Exporter e cloudflared
4. Envia arquivos e faz deploy de stacks Docker Compose no host certo
5. Move um host para outro nó do cluster mudando uma linha

Não é necessária uma VM template. As imagens cloud são baixadas direto para cada nó.

### Como ele funciona?

```bash
uv sync                          # instala o pvc
uv run pvc init                  # cria site.yml e secrets.yml
uv run pvc site apply            # baixa a imagem cloud para todos os nós
uv run pvc new blog --hosts db,app
uv run pvc up blog               # cria as VMs e as configura
```

Um serviço é um arquivo, `services/blog/service.yml`:

```yaml
defaults:
  node: pve1
  vlan: 30
  memory: 2048

hosts:
  db:
    vm_id: 1101
    ip: 172.20.30.21/24          # omita para DHCP
    roles: [compose, node_exporter]
  app:
    vm_id: 1102
    roles: [nginx, compose]
    vars:
      nginx_sites_enabled_configs: [blog.conf]
```

O `pvc up` valida o manifesto, planeja e aplica o Terraform, espera o SSH, gera o inventário do Ansible e roda um playbook em todos os hosts em paralelo. Rode de novo depois de qualquer alteração.

Leia o [Guia de configuração](docs/setup-guide.pt-br.md) e o [Guia do Usuário](docs/user-guide.pt-br.md) antes de começar.

### Comandos

| Comando | O que faz |
|---------|-----------|
| `pvc init` | Cria `site.yml` e `secrets.yml`, instala as collections do Ansible, confere os pré-requisitos |
| `pvc site apply` | Baixa as imagens cloud listadas em `site.yml` para todos os nós |
| `pvc new <svc> [--hosts a,b]` | Cria o esqueleto de `services/<svc>/service.yml` |
| `pvc validate [svc]` | Valida manifestos offline |
| `pvc plan <svc>` | Valida e roda `terraform plan` |
| `pvc up <svc>` | Aplica o Terraform e configura os hosts |
| `pvc converge <svc> [--host h] [--tags t]` | Roda só a configuração novamente |
| `pvc ssh <svc> <host>` | Entra por SSH com a chave do serviço |
| `pvc status [svc]` | Hosts, endereços e nós |
| `pvc down <svc>` | Destrói as VMs do serviço |

### Estrutura do projeto

```
pyproject.toml                  # projeto uv, entrada `pvc`
pvc/                            # a CLI
site.example.yml                # configurações do cluster (copie: site.yml, gitignored)
secrets.example.yml             # segredos (copie: secrets.yml, criptografe, gitignored)
terraform/
  site/                         # download das imagens cloud, um state para o cluster
  service/                      # um root compartilhado por todos os serviços, for_each nos hosts
  modules/proxmox-vm/           # VM + cloud-init já protegido
ansible/
  site.yml                      # o único playbook; um play por grupo de role
  roles/
services/<svc>/
  service.yml                   # o único arquivo que você edita
  filetree/                     # arquivos para todos os hosts do serviço
  hosts/<host>/filetree/        # arquivos para um host, sobrescreve o anterior
  post-deploy.sh                # opcional
  .pvc/                         # tfstate, tfvars e inventário gerado (gitignored)
```
