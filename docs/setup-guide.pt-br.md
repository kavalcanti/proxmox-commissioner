# Antes de começar

## Instale as dependências

- [uv](https://docs.astral.sh/uv/) (gerencia o Python e as dependências do `pvc`, incluindo o Ansible)
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.5 ou mais novo
- Cliente OpenSSH e OpenSSL

```bash
git clone https://github.com/kavalcanti/proxmox-commissioner
cd proxmox-commissioner
uv sync
uv run pvc init
```

O `pvc init` cria `site.yml` e `secrets.yml` a partir dos exemplos, instala as collections do Ansible em `ansible/collections/` e avisa o que estiver faltando no seu PATH.

## Configuração do PVE

Não há VM template para montar. O Terraform baixa uma imagem cloud do Debian para cada nó e a importa como disco da VM. O Proxmox precisa de três coisas:

### 1. Tipos de conteúdo do storage

As imagens cloud ficam como conteúdo `iso` e os snippets de cloud-init como `snippets`. Veja qual storage tem cada um:

```bash
pvesm status --content iso
pvesm status --content snippets
```

Se o `local` não tiver algum deles, habilite:

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```

Coloque os nomes dos storages em `site.yml`, em `storage`. `images` precisa de `iso`, `snippets` precisa de `snippets`, e `disk` e `cloudinit` precisam de conteúdo `images` (por exemplo `local-lvm`).

### 2. Um token de API

Crie um simples (e aceitavelmente inseguro) pela interface web do PVE:

1. Datacenter
2. Permissions -> API Tokens -> Add
3. User: `root@pam`
   1. Adicione um Token ID (qualquer texto)
   2. Desmarque `Privilege Separation`

Isso serve para homelab e não para produção. Para qualquer ambiente compartilhado, crie um usuário dedicado com uma role de permissões mínimas. Habilitar o QEMU guest agent exige login SSH, então o usuário deve ser `@pam`, não `@pve`. Veja a [documentação do provider BPG](https://registry.terraform.io/providers/bpg/proxmox/latest/docs) para detalhes.

Coloque o token em `secrets.yml` como `proxmox_api_token`.

### 3. Acesso SSH aos nós

O Terraform envia snippets de cloud-init e importa discos por SSH, então precisa de acesso por chave como `proxmox.ssh_user` (padrão `root`) em todos os nós listados em `site.yml`.

Tenha um `ssh-agent` rodando com a chave carregada, ou defina `proxmox.ssh_key` em `site.yml` e o `pvc` carrega essa chave em um agente temporário a cada execução (pedindo a senha, se houver).

## Configure o pvc

### site.yml

Edite endpoint, nós, storage, rede e defaults. Todos os campos estão documentados em `site.example.yml`.

### secrets.yml

```yaml
proxmox_api_token: "root@pam!pvc=<segredo>"
vault_devops_password: "<senha sudo do usuário devops>"
# vault_cloudflare_api_token: "<só para hosts com a role nginx>"
```

Depois criptografe:

```bash
uv run ansible-vault encrypt secrets.yml
```

O `pvc` lê a senha do vault do arquivo indicado em `PVC_VAULT_PASSWORD_FILE`, ou pergunta. Para editar depois: `uv run ansible-vault edit secrets.yml`.

### Baixe a imagem cloud

```bash
uv run pvc site apply
```

Isso roda uma vez, e de novo sempre que você adicionar uma imagem em `site.yml`. As imagens têm state próprio no Terraform, então destruir um serviço nunca remove uma imagem.

Lembre que os VM IDs precisam ser únicos em todo o cluster. O `pvc` confere isso entre todos os seus serviços.

O Debian é o SO para o qual as roles do Ansible foram escritas. Outras distros baseadas em Debian provavelmente funcionam se você as adicionar em `images` e apontar o `image` de um host para elas.

## Problemas comuns na configuração

- **`pvc up` falha ao importar o disco.** A imagem não foi baixada para aquele nó. Rode `pvc site apply` e confira se todos os nós usados por um serviço estão em `nodes` no `site.yml`.
- **Falha no envio do snippet.** O storage de `snippets` não tem o tipo de conteúdo `snippets`, ou o SSH para o nó falhou.
- **`qcow2` em LVM.** LVM-thin não guarda discos qcow2. Mantenha `vm.disk_format: raw` (o padrão), a menos que o storage de disco seja baseado em arquivos.
- **Um host DHCP nunca informa o endereço.** O guest agent não iniciou. Veja o console da VM atrás de erros do cloud-init, ou dê ao host um `ip` estático.
