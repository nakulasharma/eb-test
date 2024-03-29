#! /usr/bin/python
#
# Author: ankit@edgebricks.com
# (c) 2022 Edgebricks Inc


import re
import time
import pytest

from ebapi.common import utils as eutil
from ebapi.common.commands import RemoteMachine
from ebapi.common.config import ConfigParser
from ebapi.common.logger import elog
from ebapi.lib import nova
from ebapi.lib import neutron


# test settings:
# set serUserPass or serKeyFileName, not both
# set vmUserPass or vmKeyFileName, not both
testConfig = ConfigParser("qos")
iperfServerIP = testConfig.getConfig("iperfserverip")
serUserName = testConfig.getConfig("serusername")
serPassword = testConfig.getConfig("serpassword")
serKeyFile = testConfig.getConfig("serkeyfile")
iperfClientIP = testConfig.getConfig("iperfclientip")
vmUserName = testConfig.getConfig("vmusername")
vmPassword = testConfig.getConfig("vmpassword")
vmKeyFile = testConfig.getConfig("vmkeyfile")
policies = [
    # (maxBurst, maxBandwidth) in Kbps
    ("50", "500"),  # 500  Kbps throttling (10% fluctuation)
    ("100", "1000"),  # 1000 Kbps throttling (10% fluctuation)
    ("10000", "100000"),  # 100 Mbps throttling (10% fluctuation)
]
testConfig = ConfigParser()
projectID = testConfig.getProjectID()
iperfServCmd = "nohup iperf3 --server --daemon"
clientCmdOpts = "-c %s -t 20 -i 1 -f k --get-server-output" % iperfServerIP
iperfClntCmd = "iperf3 " + clientCmdOpts
# following test settings will be automatically populated
iperfServer = None
iperfClient = None
selectedVM = None


@pytest.fixture(scope="module")
def setup_test(request):  # pylint: disable=too-many-branches
    notset = False
    testParams = {
        "vmUserName": vmUserName,
        "serUserName": serUserName,
        "iperfServerIP": iperfServerIP,
    }

    serverObj = nova.VMs(projectID)

    global iperfClientIP, iperfServer, iperfClient, selectedVM  # pylint: disable=global-statement
    if not iperfClientIP:
        vms = serverObj.getAllVMs()
        vmIDs = vms.keys()
        for vmID in vmIDs:
            floatingIP = serverObj.getFloatingIPFromVMID(vmID)
            if floatingIP:
                selectedVM = vmID
                iperfClientIP = floatingIP
                break
    else:
        selectedVM = serverObj.getVMIDFromFloatingIP(iperfClientIP)

    if not selectedVM:
        pytest.skip("failed to find any VMS with floating IP")

    if serPassword:
        iperfServer = RemoteMachine(iperfServerIP, serUserName, serPassword)
    elif serKeyFile:
        iperfServer = RemoteMachine(iperfServerIP, serUserName, keyfile=serKeyFile)
    else:
        pytest.skip("set test param serPassword or serKeyFile")

    if vmPassword:
        iperfClient = RemoteMachine(iperfClientIP, vmUserName, vmPassword)
    elif vmKeyFile:
        iperfClient = RemoteMachine(iperfClientIP, vmUserName, keyfile=vmKeyFile)
    else:
        pytest.skip("set test param vmPassword or vmKeyFile")

    for key, value in testParams.items():
        if not value:
            elog.error("%s not set" % key)
            notset = True

    if notset:
        pytest.skip("test params not set")

    rc, _ = iperfServer.run("which iperf3")
    if rc != 0:
        pytest.skip(
            "iperf3 not installed on iperfServer: %s" % eutil.bcolor(iperfServerIP)
        )

    rc, _ = iperfClient.run("which iperf3")
    if rc != 0:
        pytest.skip(
            "iperf3 not installed on iperfClient: %s" % eutil.bcolor(iperfClientIP)
        )

    iperfServer.run("killall iperf3; rm server.out")
    rc, _ = iperfServer.run(iperfServCmd)
    if rc != 0:
        pytest.skip("failed to start iperf server")

    rc, _ = iperfServer.run("netstat -anp | grep 5201")
    if rc != 0:
        pytest.skip("netstat output failed to show iperf server port 5201")

    elog.info("iperf3 running on server %s" % eutil.bcolor(iperfServerIP))

    def cleanup():
        iperfServer.run("killall iperf3; rm server.out")

    request.addfinalizer(cleanup)


def getBandwidth(output):
    match = re.findall(".*receiver", output, re.M)
    if not match:
        elog.error("no receiver information in server log")
        return None
    sender = match.pop()
    match = re.findall(r"(\S+\s.bits/sec)", sender, re.M)
    if not match:
        elog.error("no bandwidth information in server log")
        return None

    return match.pop()


@pytest.mark.parametrize("maxBurst, maxBandwidth", policies)
def test_bandwidth(maxBurst, maxBandwidth):
    serverObj = nova.VMs(projectID)
    macAddr = serverObj.getMacAddrFromIP(selectedVM, iperfClientIP)
    assert macAddr
    elog.info(
        "macAddr of VM %s with FloatingIP %s = %s"
        % (eutil.bcolor(selectedVM), eutil.bcolor(iperfClientIP), eutil.bcolor(macAddr))
    )

    portObj = neutron.Ports(projectID)
    portID = portObj.getPortIDByMacAddress(macAddr)
    assert portID
    elog.info("portID of VM %s = %s" % (eutil.bcolor(selectedVM), eutil.bcolor(portID)))

    elog.info("getting bandwidth without any QoS Policy")
    rc, output = iperfClient.run(iperfClntCmd)
    assert rc == 0
    assert output

    bandwidth = getBandwidth(output)
    assert bandwidth
    elog.info("bandwidth without any QoS Policy = %s" % eutil.bcolor(bandwidth))

    qosObj = neutron.QoS()
    name = maxBandwidth + "kbps-limit"
    policyID = qosObj.createPolicy(name)
    assert policyID
    elog.info("QoS policyID = %s" % eutil.bcolor(policyID))

    assert qosObj.createBandwidthLimitRules(policyID, maxBurst, maxBandwidth)
    elog.info("successfully created bandwidth limit rules")

    assert portObj.attachQoSPolicy(portID, policyID)
    elog.info(
        "successfully attached QoS policy %s to port %s"
        % (eutil.bcolor(policyID), eutil.bcolor(portID))
    )

    time.sleep(2)
    elog.info("getting bandwidth with QoS Policy")
    rc, output = iperfClient.run(iperfClntCmd)
    assert rc == 0

    bandwidth = getBandwidth(output)
    assert bandwidth
    elog.info("bandwidth with QoS Policy = %s" % eutil.bcolor(bandwidth))

    assert portObj.detachQoSPolicy(portID)
    elog.info(
        "successfully detached QoS policy %s from port %s"
        % (eutil.bcolor(policyID), eutil.bcolor(portID))
    )

    assert qosObj.deletePolicy(policyID)
    elog.info("successfully deleted QoS policy %s" % eutil.bcolor(policyID))
