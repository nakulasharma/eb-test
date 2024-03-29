#! /usr/bin/python
#
# Author: ankit@edgebricks.com
# Copyright (c) 2021-2023 Edgebricks Inc.

import pytest

from ebapi.common.config import ConfigParser
from ebapi.lib.edgebricks import BUs


class TestBuCRUD:
    testConfig = ConfigParser()

    def test_bu_crud_001(cls):
        try:
            # create bu using config
            buObj = BUs()
            domainName = cls.testConfig.getDomainName()
            buID = buObj.create(buName=domainName)
            assert buID

            # get bu
            buResp = buObj.get(buID)
            assert buResp["name"] == domainName

            # wait for bu to be created
            assert buObj.waitForState(buID, state=BUs.BU_STATE_CREATED)

            # update bu description
            newDesc = "ebtestDomain description updated"
            updatedBuResp = buObj.update(buID, desc=newDesc, buName=domainName)
            assert updatedBuResp["description"] == newDesc

            # get bu quota
            quotaURL = buID + "/quotas"
            buResp = buObj.get(quotaURL)
            assert bool(buResp)

            # update bu quota
            quotaTemplate = "Medium"
            updatedBuResp = buObj.updateQuota(buID, quotaTemplate=quotaTemplate)
            assert updatedBuResp["quota_sets"]["selected_template"] == quotaTemplate

            # get updated bu quota
            quotaURL = buID + "/quotas"
            buResp = buObj.get(quotaURL)
            assert buResp["quota_sets"]["selected_template"] == quotaTemplate

        finally:
            # delete bu
            assert buObj.delete(buID)

            # wait for bu to be deleted
            assert buObj.waitForState(buID, state=BUs.BU_STATE_DELETED)

    @pytest.mark.parametrize(
        "buNames", ["ebtestDomainNew01", "ebtestDomainNew02", "ebtestDomainNew03"]
    )
    def test_bu_crud_002(cls, buNames):
        try:
            # create bu
            buObj = BUs()
            buID = buObj.create(buName=buNames)
            assert buID

            # wait for bu to be created
            assert buObj.waitForState(buID, state=BUs.BU_STATE_CREATED)

            # get bu aggregates
            aggregateURL = buID + "?aggregates=true&quota=true"
            buResp = buObj.get(aggregateURL)
            assert buResp["name"] == buNames

            # reload bu
            reloadURL = buID + "?aggregates=true&quota=true&nocache=true"
            buResp = buObj.get(reloadURL)
            assert buResp["name"] == buNames

        finally:
            # delete bu
            assert buObj.delete(buID)

            # wait for bu to be deleted
            assert buObj.waitForState(buID, state=BUs.BU_STATE_DELETED)
