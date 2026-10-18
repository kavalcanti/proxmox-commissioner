# Before you begin

## Install dependencies

- [uv](https://docs.astral.sh/uv/) (manages Python and the `pvc` dependencies, including Ansible)
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.5 or newer
- OpenSSH client and OpenSSL

```bash
git clone https://github.com/kavalcanti/proxmox-commissioner
cd proxmox-commissioner
uv sync
uv run pvc init
```

`pvc init` creates `site.yml` and `secrets.yml` from the examples, installs the Ansible collections into `ansible/collections/`, and reports anything missing from your PATH.

## PVE configuration

Terraform downloads a Debian cloud image to each node and imports it as the VM disk. 
Before you start requirements:

### 1. Storage content types

Cloud images are stored as `iso` content and cloud-init snippets as `snippets` content. 
To check which storage has them:

```bash
pvesm status --content iso
pvesm status --content snippets
```

If `local` is missing either, enable them:

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```

Put the storage names in `site.yml` under `storage`. `images` needs `iso`, `snippets` needs `snippets`, and `disk` and `cloudinit` need `images` content (for example `local-lvm`).

### 2. An API token

Get a simple (and acceptably unsafe) one from the PVE web UI:

1. Datacenter
2. Permissions -> API Tokens -> Add
3. User: `root@pam`
   1. Add a Token ID (any string)
   2. Uncheck `Privilege Separation`

This is fine for a homelab and not for production. For anything shared, create a dedicated user with a minimal role instead. Enabling the QEMU guest agent needs SSH login, so the user should be `@pam`, not `@pve`. See the [BPG provider documentation](https://registry.terraform.io/providers/bpg/proxmox/latest/docs) for details.

Put the token in `secrets.yml` as `proxmox_api_token`.

### 3. SSH access to the nodes

Terraform uploads cloud-init snippets and imports disks over SSH, so it needs key access as `proxmox.ssh_user` (default `root`) on every node listed in `site.yml`.

Either have an `ssh-agent` running with the key loaded, or set `proxmox.ssh_key` in `site.yml` and `pvc` will load that key into a temporary agent for each run (asking for the passphrase if it has one).

## Configure pvc

### site.yml

Edit the endpoint, nodes, storage, network and defaults. Every field is documented in `site.example.yml`.

### secrets.yml

```yaml
proxmox_api_token: "root@pam!pvc=<secret>"
vault_devops_password: "<sudo password for the devops user>"
# vault_cloudflare_api_token: "<only for hosts with the nginx role>"
```

Then encrypt it:

```bash
uv run ansible-vault encrypt secrets.yml
```

`pvc` reads the vault password from the file named by `PVC_VAULT_PASSWORD_FILE`, or asks for it. Edit later with `uv run ansible-vault edit secrets.yml`.

### Download the cloud image

```bash
uv run pvc site apply
```

This runs once, and again whenever you add an image to `site.yml`. Images have their own Terraform state, so destroying a service never removes one.

Note VM IDs must be unique across the whole cluster. `pvc` checks this across all your services.

Debian is the OS the Ansible roles are written for. Other Debian-based distros will probably work if you add them under `images` and point a host's `image` at them.

## PCI passthrough host preparation

Only needed for hosts that use `pci_devices` (see the [user guide](user-guide.md#pci-passthrough)). `pvc` does not change the Proxmox nodes' kernel configuration, because it needs a reboot.

1. Enable the IOMMU in the BIOS (VT-d on Intel, AMD-Vi / IOMMU on AMD).
2. Add kernel parameters. For Intel, in `/etc/default/grub` (`GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"`) then `update-grub`, or in `/etc/kernel/cmdline` followed by `proxmox-boot-tool refresh` on systemd-boot installs. AMD enables the IOMMU by default, `iommu=pt` is enough.
3. Load the VFIO modules by adding `vfio`, `vfio_iommu_type1` and `vfio_pci` to `/etc/modules`, then reboot.
4. Check it worked with `dmesg | grep -e DMAR -e IOMMU`.
5. Find the device values for `site.yml` with `lspci -Dnn` (the address, such as `0000:00:02.0`, and the `[8086:4680]` ids), and the group with `find /sys/kernel/iommu_groups/ -type l | grep 0000:00:02.0`.

The API token needs permission to manage mappings (`Mapping.Modify`, and `Mapping.Use` to attach them). The `root@pam` token without privilege separation from step 2 already has both.

## Known setup pitfalls

- **`pvc up` fails importing the disk.** The image has not been downloaded to that node. Run `pvc site apply`, and make sure every node a service uses is listed under `nodes` in `site.yml`.
- **Snippet upload fails.** The `snippets` storage does not have the `snippets` content type, or SSH to the node failed.
- **`qcow2` on LVM.** LVM-thin cannot hold qcow2 disks. Keep `vm.disk_format: raw` (the default) unless the disk storage is file based.
- **A DHCP host never reports an address.** The guest agent has not started. Check the VM console for cloud-init errors, or give the host a static `ip`.
