function Handler($context, $inputs) {
    $vcHostname = $inputs.vcHostname
    $vcUsername = $inputs.vcUsername
    $vcPassword = $inputs.vcPassword
    $vmName = $inputs.vmName
    $folderPath = $inputs.folderName

    Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -Confirm:$false | Out-Null
    Connect-VIServer $vcHostname -User $vcUsername -Password $vcPassword | Out-Null

    $vm = Get-VM -Name "$vmName"

    $datacenter = Get-Datacenter -VM $vm
    $folderRoot = Get-Folder -Name "vm" -Location $datacenter

    $folders = $folderPath -split '/'
    $currentFolder = $folderRoot

    foreach ($folder in $folders) {
        $checkFolder = Get-Folder -Name $folder -Location $currentFolder -ErrorAction SilentlyContinue
        if (-not $checkFolder) {
            $checkFolder = New-Folder -Name $folder -Location $currentFolder
        }
        $currentFolder = $checkFolder
    }

    Move-VM -VM $vm -Destination $currentFolder | Out-Null

    Write-Output "VM PowerOn and moved to folder path: $folderPath"
}
