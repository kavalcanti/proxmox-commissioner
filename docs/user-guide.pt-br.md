# Guia do Usuário

Rode tudo a partir da raiz do projeto com `uv run pvc ...`, ou ative o ambiente virtual (`source .venv/bin/activate`) e chame `pvc` diretamente.

## Conceitos

- **Site**: o cluster. O `site.yml` guarda endpoint do Proxmox, nós, storage, rede e defaults compartilhados por tudo.
- **Serviço**: um grupo de VMs gerenciadas juntas, como um banco de dados e o app que o usa. Vive em `services/<nome>/` e é descrito por um arquivo, `service.yml`. Cada serviço tem seu próprio state do Terraform e pode ser criado e destruído de forma independente.
- **Host**: uma VM de um serviço.
- **Role**: uma funcionalidade que o host escolhe (`docker`, `nginx`, ...). Todo host recebe também `base`: hardening, pacotes e envio de arquivos.

```
services/<servico>/
  service.yml                  # o único arquivo que você edita
  filetree/                    # arquivos enviados a todos os hosts do serviço
  hosts/<host>/filetree/       # arquivos enviados a um host, sobrescrevem filetree/
  post-deploy.sh               # opcional, roda em todos os hosts com --post-deploy
  hosts/<host>/post-deploy.sh  # opcional, substitui o script do serviço para esse host
  .pvc/                        # gerado: state do terraform, tfvars, inventário (gitignored)
```

> `services/<servico>/.pvc/terraform.tfstate` é o único registro do que existe no Proxmox para aquele serviço. Faça backup.

## Fluxo de trabalho

```bash
pvc new meuservico --hosts db,app        # 1. cria services/meuservico/service.yml
$EDITOR services/meuservico/service.yml  # 2. descreva os hosts
pvc validate meuservico              # 3. opcional: confere sem tocar no Proxmox
pvc up meuservico                    # 4. cria as VMs e as configura
pvc converge meuservico              # 5. roda a configuração de novo quando quiser
pvc down meuservico                  # 6. destrói as VMs
```

O `pvc up` faz, em ordem:

1. Valida o `service.yml` contra o `site.yml` e os outros serviços (`vm_id`, IP ou nome de VM duplicado, role desconhecida, nó desconhecido)
2. Cria `~/.ssh/pvc/<servico>` (ed25519) se não existir
3. Roda `terraform apply`, que pede aprovação (`-y` dispensa)
4. Espera todos os hosts aceitarem SSH na porta final
5. Escreve `services/<servico>/.pvc/inventory.yml` a partir do manifesto e da saída do Terraform
6. Roda `ansible/site.yml` em todos os hosts do serviço em paralelo

Toda VM sobe já protegida pelo cloud-init: um usuário sudo `devops` com a chave do serviço, SSH só com chave em `ssh.port`, root bloqueado. Não existe fase de bootstrap insegura, então rodar qualquer comando de novo é sempre seguro.

## O manifesto

```yaml
defaults:                  # vale para todos os hosts deste serviço
  node: pve1
  cores: 2
  memory: 2048
  vlan: 30

hosts:
  db:
    vm_id: 1101            # obrigatório, único no cluster
    ip: 172.20.30.21/24    # CIDR para IP estático; omita ou "dhcp" para DHCP
    disk: 32
    roles: [compose, node_exporter]
    vars:                  # variáveis Ansible deste host
      additional_packages: [postgresql-client]
  app:
    vm_id: 1102
    node: pve2             # sobrescreve defaults.node
    roles: [nginx, compose]
    vars:
      nginx_sites_enabled_configs: [blog.conf]
```

Os valores são resolvidos nesta ordem, o último vence: `defaults` do `site.yml`, `defaults` do `service.yml`, o próprio host. As `roles` são somadas entre as camadas e as `vars` são mescladas chave a chave.

| Campo | Padrão | Observações |
|-------|--------|-------------|
| `vm_id` | nenhum | Obrigatório. 100 ou mais |
| `name` | `<servico>-<host>` | Nome da VM e hostname |
| `node` | o único nó do `site.yml` | Obrigatório se o `site.yml` listar vários |
| `ip` | DHCP | CIDR IPv4. IP estático exige gateway |
| `gateway` | `network.gateway` | |
| `cores`, `sockets` | 1, 1 | |
| `memory` | 1024 | MB, no mínimo 512 |
| `disk` | 16 | GB, no mínimo 8 |
| `vlan` | 0 | 0 significa sem tag |
| `bridge` | `network.bridge` | |
| `image` | primeira imagem do `site.yml` | Uma chave de `images` |
| `roles` | nenhuma | Veja a tabela abaixo |
| `vars` | nenhuma | Variáveis de host para o Ansible |

Campos desconhecidos são erro, então um typo como `memroy` é pego antes de qualquer coisa acontecer.

### Roles

| Role | Instala ou configura | Variáveis |
|------|----------------------|-----------|
| `base` (sempre) | Drop-in do SSH e UFW, atualizações automáticas, fail2ban, pacotes e serviços extras, envio de arquivos | `additional_packages`, `additional_services` |
| `nfs` | Cliente NFS e montagens | `nfs_mountpoints` |
| `docker` | Docker engine e plugin compose | `docker_users` |
| `compose` | `docker compose up` da stack no filetree. Implica `docker` | `docker_deploy_compose_dir`, `docker_deploy_pull`, `docker_deploy_force_recreate` |
| `nginx` | nginx, certbot, certificado wildcard DNS-01 do Cloudflare, sites habilitados | `nginx_sites_enabled_configs`, `webserver_cert_name`, `webserver_cert_email`, `webserver_cert_domain_wildcard`, segredo `vault_cloudflare_api_token` |
| `cloudflared` | Cliente do Cloudflare Tunnel | |
| `node_exporter` | Prometheus Node Exporter | `node_exporter_listen_address`, `node_exporter_open_ufw`, `node_exporter_ufw_from` |
| `kubernetes` | Pacotes do Kubernetes | |
| `gitlab` | Pacote Linux do GitLab no Debian (Community ou Enterprise Edition), UFW para HTTP, HTTPS e Git SSH | `gitlab_edition`, `gitlab_external_url`, `gitlab_root_email`, segredo `vault_gitlab_root_password` |

Variáveis compartilhadas, como as do certificado, ficam em `ansible_vars` no `site.yml`; as de cada host ficam em `vars`.

Um exemplo de NFS, em que um host monta um compartilhamento:

```yaml
hosts:
  media:
    vm_id: 1200
    roles: [nfs, compose]
    vars:
      nfs_mountpoints:
        - name: media
          server: 172.20.30.5
          export: /exports/media
          mount_point: /mnt/media
          options: [vers=4, proto=tcp, noatime]
```

Os valores podem referenciar outros hosts do serviço via `hostvars`, usando o nome da VM como nome do host:

```yaml
vars:
  nfs_mountpoints:
    - server: "{{ hostvars['blog-db'].ansible_host }}"
      export: /exports/blog
      mount_point: /mnt/blog
```

IPs estáticos deixam esses endereços estáveis e conhecidos antes de as VMs existirem.

## Arquivos

Tudo em `filetree/` é enviado à VM no mesmo caminho absoluto, depois de o software ser instalado e antes de nginx e compose serem configurados:

- `filetree/home/devops/...` é copiado para `/home/devops/...`, com o usuário sudo como dono
- qualquer outro diretório de primeiro nível, como `filetree/etc/nginx/sites-available/blog.conf`, é copiado para `/etc/nginx/sites-available/blog.conf`, com `root` como dono

`services/<servico>/filetree/` vai para todos os hosts. `services/<servico>/hosts/<host>/filetree/` vai só para aquele host e vence em conflitos. Um par db e app normalmente fica assim:

```
services/blog/
  hosts/db/filetree/home/devops/blog/docker-compose.yml     # postgres
  hosts/app/filetree/home/devops/blog/docker-compose.yml    # o app
  hosts/app/filetree/etc/nginx/sites-available/blog.conf
```

A role `compose` sobe a stack em `/home/devops/<servico>/docker-compose.yml` (mude com `docker_deploy_compose_dir`).

## Scripts de post-deploy

O `post-deploy.sh` é imperativo e pode não ser idempotente, então só roda quando pedido:

```bash
pvc up meuservico --post-deploy
pvc converge meuservico --post-deploy
```

Roda em todos os hosts como root. Um `hosts/<host>/post-deploy.sh` substitui o script do serviço para aquele host.

## Rodando parte da configuração

```bash
pvc converge blog                         # tudo, todos os hosts
pvc converge blog --host app              # um host
pvc converge blog --tags nginx            # uma etapa
pvc converge blog --host app -t files -t compose
```

| Tag | Etapa |
|-----|-------|
| `base` | Tudo do play base. Também `ssh`, `autoupdates`, `fail2ban`, `packages`, `services` |
| `nfs`, `docker`, `cloudflared`, `kubernetes`, `gitlab` | A role correspondente |
| `node_exporter` (ou `monitoring`) | Node Exporter |
| `nginx` | Instalação e configuração dos sites do nginx. Também `webserver` e `webserver-config` separadamente |
| `files` | Envio de arquivos |
| `compose` | Deploy do compose |
| `post_deploy` | Script de post-deploy (exige `--post-deploy`) |

O `pvc converge` nunca toca no Proxmox, então é rápido. Use `pvc up` quando o `service.yml` mudar hardware, rede ou nós.

## Vários nós

Defina `node` por host (ou em `defaults`). O Terraform cria cada VM direto no seu nó, usando a imagem baixada lá. Todo nó precisa estar listado no `site.yml`.

Mudar o `node` de um host e rodar `pvc up` faz migração ao vivo da VM em vez de recriá-la.

## Arquivos de configuração

| Arquivo | Finalidade |
|---------|------------|
| `site.yml` | Endpoint do Proxmox, nós, storage, rede, imagens, porta e usuário SSH, tamanhos padrão de VM, variáveis Ansible compartilhadas |
| `secrets.yml` | Criptografado com ansible-vault: `proxmox_api_token`, `vault_devops_password`, `vault_cloudflare_api_token` |
| `services/<svc>/service.yml` | Hosts de um serviço |

A senha sudo vira hash (SHA-512 crypt) no cloud-init e também é a senha de `become` do Ansible. O token da API chega ao Terraform como variável de ambiente, nunca em arquivo.

## Inspecionando e depurando

```bash
pvc status                  # hosts, endereços e nós de cada serviço
pvc ssh blog app            # shell em um host
pvc ssh blog app journalctl -u docker --no-pager -n 50
pvc plan blog               # o que o Terraform mudaria
```

O `services/<svc>/.pvc/inventory.yml` é regenerado a cada execução e não deve ser editado. Coloque variáveis de host em `vars` no `service.yml`.

Para rodar o Ansible à mão contra um serviço:

```bash
cd ansible
uv run ansible-playbook -i ../services/blog/.pvc/inventory.yml site.yml -e @../secrets.yml --ask-vault-pass --limit svc_blog_app --tags nginx
```

## Destruindo um serviço

```bash
pvc down blog
```

Remove as VMs e o inventário gerado. O `service.yml`, o filetree e a chave SSH permanecem, então `pvc up blog` traz o serviço de volta.
