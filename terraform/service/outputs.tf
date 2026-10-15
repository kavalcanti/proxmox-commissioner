output "hosts" {
  description = "Manifest host name => address and placement. Consumed by pvc to build the Ansible inventory."
  value = {
    for key, vm in module.vm : key => {
      name  = vm.vm_name
      vm_id = vm.vm_id
      node  = vm.vm_node
      ip    = vm.vm_ip
      mac   = vm.vm_mac_address
    }
  }
}
