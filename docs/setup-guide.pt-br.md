# Antes de começar

## Instale as dependências

Certifique-se de instalar o Ansible e o Terraform antes de começar.

## Configuração do PVE

Siga estes passos obrigatórios no host do seu Proxmox Virtual Environment antes de usar o Proxmox Commissioner.

## Crie um template com cloud-init

Há um script utilitário para isso em `scripts/vm-templates/debian.sh`.
Você pode copiar o arquivo (ou o conteúdo dele) para o host PVE e executá-lo.
Isso também pode ser feito no shell local ou via SSH:

``` bash
# Criando manualmente uma VM template no shell do PVE
# Baixe a imagem cloud do Debian
cd /tmp
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2

# Importe como template de VM (cria o VM ID 9000)
qm create 9000 --name debian-13-cloud --memory 1024 --cores 1 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-13-generic-amd64.qcow2 local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --agent enabled=1
qm set 9000 --vga qxl

# Converta em template
qm template 9000

# Limpeza
rm debian-13-generic-amd64.qcow2
```

Observação: os IDs de VM devem ser únicos tanto em um único nó quanto em todo o cluster.
Debian é o sistema que eu geralmente uso para servidores, mas a automação com Ansible neste repositório provavelmente funciona para qualquer distro baseada em Debian.

O Terraform também deve funcionar com outras distros, desde que os templates e padrões sejam ajustados.

## Credenciais do Proxmox

Você precisará criar um token de API do Proxmox.

Você pode gerar um token simples (e aceitavelmente inseguro) na WebUI do PVE:
1. Datacenter
2. Permissions -> API Tokens -> Add
3. Selecione o usuário: root@pam
   3.1. Adicione um Token ID (qualquer string serve)
   3.2. Desmarque `Privilege Separation`

Isso cria uma chave insegura, mas funcional, que serve para homelabs, porém não para produção.
Recomendo criar um usuário separado para o Terraform e usar uma role dedicada ao Terraform com permissões mínimas.
Ativar o QEMU Agent exige login por SSH, então o usuário deve ser @PAM, e não @PVE.

Para detalhes sobre como configurar uma autenticação mais segura, consulte a [documentação da BPG](https://registry.terraform.io/providers/bpg/proxmox/0.37.1/docs).

## Problemas comuns de configuração

Pode ser necessário ajustar alguns detalhes para disponibilizar cloud-init no Proxmox. O armazenamento (local ou local-lvm) pode não estar configurado para snippets.

Verifique se o armazenamento de snippets está configurado no host Proxmox com:

```bash
pvesm status --content snippets
```

Se nenhum armazenamento estiver configurado, execute:

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```
