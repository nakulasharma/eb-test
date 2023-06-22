#! /usr/bin/env python


# Author: ankit@edgebricks.com
# (c) 2022 Edgebricks


import json

from ebtest.common import utils as eutil
from ebtest.common import logger as elog
from ebtest.common.rest import RestClient
from ebtest.lib.keystone import Token


class NovaBase(Token):
    def __init__(self, projectID, scope='project'):
        super(NovaBase, self).__init__(scope)
        self.client     = RestClient(self.getToken())
        self.projectID  = projectID
        self.apiURL     = self.getApiURL()
        self.serviceURL = self.getServiceURL()
        self.novaURL    = self.serviceURL + '/nova/v2/' + self.projectID
        self.clusterID  = self.getClusterID()
        self.clusterURL = self.apiURL + '/v2/clusters/' + self.clusterID


class VMs(NovaBase):
    def __init__(self, projectID):
        super(VMs, self).__init__(projectID)
        self.vmsURL      = self.clusterURL + '/projects'
        self.serversURL  = self.novaURL + '/servers'

    def getAllVMs(self):
        response = self.client.get(self.vmsURL + '/' + self.projectID + '/vms')
        if not response.ok:
            elog.logging.error('failed to get all VMs: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        content = json.loads(response.content)
        vms = {}
        for vm in content:
            vms[vm['id']] = vm['name']

        return vms

    def getVM(self, vmID):
        requestURL = self.clusterURL + '/vms/' + vmID
        return self.client.get(requestURL)

    def getFloatingIPFromVMID(self, vmID):
        requestURL = self.novaURL + '/os-floating-ips'
        response   = self.client.get(requestURL)
        if not response.ok:
            elog.logging.error('failed fetching VM details for %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            return None

        content = json.loads(response.content)
        for floatingIP in content['floating_ips']:
            instanceID = floatingIP['instance_id']
            if instanceID == vmID:
                return floatingIP['ip']

        elog.logging.error('no floating IP assigned to %s' % eutil.bcolor(vmID))
        return None

    def getVMIDFromFloatingIP(self, fip):
        requestURL = self.novaURL + '/os-floating-ips'
        response   = self.client.get(requestURL)
        if not response.ok:
            elog.logging.error('failed fetching VM details for %s: %s'
                       % (eutil.bcolor(fip),
                          eutil.rcolor(response.status_code)))
            return None

        content = json.loads(response.content)
        for floatingIP in content['floating_ips']:
            ip = floatingIP['ip']
            if ip == fip:
                return floatingIP['instance_id']

        elog.logging.error('no VM assigned with floatingIP %s' % eutil.bcolor(fip))
        return None

    def getMacAddrFromIP(self, vmID, ipAddr):
        response = self.getVM(vmID)
        if not response.ok:
            elog.logging.error('fetching vm details for %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        content = json.loads(response.content)
        for netname in content['addresses']:
            for element in content['addresses'][netname]:
                if element['Addr'] == ipAddr:
                    return element['OS-EXT-IPS-MAC:mac_addr']

        elog.logging.error('no mac address found for %s' % eutil.bcolor(ipAddr))
        return None

    def getVolumesAttached(self, vmID):
        response = self.getVM(vmID)
        if not response.ok:
            elog.logging.error('fetching VM details for %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        content  = json.loads(response.content)
        lvolumes = []
        for vols in content['volumes']:
            lvolumes.append(vols['id'])

        return lvolumes

    def getStatus(self, vmID):
        response = self.getVM(vmID)
        if not response.ok:
            elog.logging.error('fetching VM details for %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        content  = json.loads(response.content)
        return content['vm_state']

    def getHost(self, vmID):
        response = self.getVM(vmID)
        if not response.ok:
            elog.logging.error('fetching VM details for %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        content  = json.loads(response.content)
        return content['host']

    def createVM(self, vmName = '', flavorID = '', networkID = '', imageID = ''):
        requestURL = self.vmsURL + '/' + self.projectID + '/vm'
        payload = {
            "name": vmName,
            "resources": {
                "server": {
                    "type": "OS::Nova::Server",
                    "os_req": {
                        "server": {
                            "name": vmName,
                            "flavorRef": flavorID,
                            "block_device_mapping_v2": [
                                {
                                    "device_type": "disk",
                                    "disk_bus": "virtio",
                                    "device_name": "/dev/vda",
                                    "source_type": "volume",
                                    "destination_type": "volume",
                                    "delete_on_termination": True,
                                    "boot_index": "0",
                                    "uuid": "{{.bootVol}}"
                                }
                            ],
                            "networks": [
                                {
                                    "uuid": networkID
                                }
                            ],
                            "security_groups": [
                                {
                                    "name": "default"
                                }
                            ]
                        },
                        "os:scheduler_hints": {
                            "volume_id": "{{.bootVol}}"
                        }
                    }
                },
                "bootVol": {
                    "type": "OS::Cinder::Volume",
                    "os_req": {
                        "volume": {
                            "availability_zone": None,
                            "description": None,
                            "size": 1,
                            "name": "bootVolume-" + vmName,
                            "volume_type": "relhighiops_type",
                            "disk_bus": "virtio",
                            "device_type": "disk",
                            "source_type": "image",
                            "device_name": "/dev/vda",
                            "bootable": True,
                            "tenant_id": self.projectID,
                            "imageRef": imageID,
                            "enabled": "true"
                        }
                    }
                }
            }
        }
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('creating vm %s: %s'
                       % (eutil.bcolor(vmName),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('creating vm %s: %s OK'
                  % (eutil.bcolor(vmName),
                     eutil.gcolor(response.status_code)))
        return True

    def deleteVM(self, vmID):
        requestURL = self.vmsURL + '/' + self.projectID + '/vm/' + vmID
        response   = self.client.delete(requestURL)
        if not response.ok:
            elog.logging.error('deleting vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('deleting vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def suspendVM(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"suspend": ""}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('suspending vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('suspending vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def resumeVM(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"resume": ""}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('resuming vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('resuming vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def rebootVM(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"reboot":{"type":"SOFT"}}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('reboot vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('reboot vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def powerOffVM(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"os-stop": ""}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('poweroff vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('poweroff vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def powerOnVM(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"os-start": ""}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('poweron vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('poweron vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def migrateVM(self, vmID, doc=False, bm=False, host=None):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {
            "os-migrateLive": {
                "host"            : host,
                "block_migration" : bm,
                "disk_over_commit": doc
            }
        }
        response = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('migrate vm %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('migrate vm %s: %s OK'
                  % (eutil.bcolor(vmID),
                     eutil.gcolor(response.status_code)))
        return True

    def getVMConsole(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/action'
        payload    = {"os-getVNCConsole": {"type": "novnc"}}
        response   = self.client.post(requestURL, payload)
        if not response.ok:
            elog.logging.error('failed getting console for VM %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        content = json.loads(response.content)
        return content['console']['url']

    def getOSInterfaces(self, vmID):
        requestURL = self.serversURL + '/' + vmID + '/os-interface'
        response   = self.client.get(requestURL)
        if not response.ok:
            elog.logging.error('failed getting os-interface info for VM %s: %s'
                       % (eutil.bcolor(vmID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        return response

    def getPortIDFromNetID(self, vmID, networkID):
        response = self.getOSInterfaces(vmID)
        if not response:
            return None

        content = json.loads(response.content)

        for interface in content['interfaceAttachments']:
            if interface['net_id'] == networkID:
                return interface['port_id']

        return None


class Flavors(NovaBase):
    def __init__(self, projectID):
        super(Flavors, self).__init__(projectID)
        self.flavorsURL = self.serviceURL + '/nova/v2.1/' + self.projectID + '/flavors'

    def getFlavorsDetail(self):
        requestURL = self.flavorsURL + '/detail'
        return self.client.get(requestURL)

    def getBestMatchingFlavor(self, numCPU, memMB):
        response = self.getFlavorsDetail()
        if not response.ok:
            elog.logging.error('fetching flavor details failed: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        dflavor = {}
        content = json.loads(response.content)
        for flavors in content['flavors']:
            dflavor[flavors['id']] = [flavors['vcpus'], flavors['ram']]

        if not dflavor:
            return None

        bestMatchFlavor = []
        flavorID = ''
        for key, lvalues in dflavor.items():
            flCPU = lvalues[0]
            flMEM = lvalues[1]
            if numCPU <= flCPU and memMB <= flMEM:
                if not bestMatchFlavor or flCPU < bestMatchFlavor[0] or \
                        flMEM < bestMatchFlavor[1]:
                    bestMatchFlavor = []
                    flavorID        = key
                    bestMatchFlavor.append(flCPU)
                    bestMatchFlavor.append(flMEM)

        if bestMatchFlavor:
            return flavorID
        else:
            return None