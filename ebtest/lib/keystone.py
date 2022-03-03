#! /usr/bin/env python


# Author: ankit@edgebricks.com
# (c) 2022 Edgebricks


import json
import requests

from ebtest.common import utils as eutil
from ebtest.common.config import ConfigParser
from ebtest.common import logger as elog
from ebtest.common.rest import RestClient


class KeystoneBase(ConfigParser):
    """
    class that implements CRUD operation for keystone.
    """
    def __init__(self):
        super(KeystoneBase, self).__init__()
        serviceURL       = self.getServiceURL()
        keystoneVer      = '/keystone/v3'
        self.keystoneURL = serviceURL + keystoneVer


class Token(KeystoneBase):
    """
    class that implements CRUD operation for Token.
    """
    def __init__(self, scope='domain', domainName='', user='', password='',
                 projectName=''):
        super(Token, self).__init__()
        self.scope       = scope
        self.domainName  = domainName
        self.projectName = projectName
        self.user        = user
        self.password    = password

        if not self.domainName:
            self.domainName  = self.getDomainName()
        if not self.projectName:
            self.projectName = self.getProjectName()
        if not self.user:
            self.user        = self.getProjectAdmin()
        if not self.password:
            self.password    = self.getProjectAdminPassword()

        self.tokenURL = self.keystoneURL + '/auth/tokens'
        self.token    = self.getToken()

    def getPayloadWithDomainScope(self):
        # return payload with domain scope
        payload = {
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "domain": {
                                "name": self.domainName
                            },
                            "name": self.user,
                            "password": self.password
                        }
                    }
                },
                "scope": {
                    "domain": {
                        "name": self.domainName
                    }
                }
            }
        }
        return payload

    def getPayloadWithProjectScope(self):
        # return payload with project scope
        payload = {
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "domain": {
                                "name": self.domainName
                            },
                            "name": self.user,
                            "password": self.password
                        }
                    }
                },
                "scope": {
                    "project": {
                        "name": self.projectName,
                        "domain": {
                            "name": self.domainName
                        }
                    }
                }
            }
        }
        return payload

    def getToken(self):
        '''
        Returns:
            method that returns a project or domain scope token. default is
            domain scope token.

        Examples:
            domain level scope::

                tokenObj = Token('domain', domainName, userName, userPassword)

            project level scope::

                tokenObj = Token('project', domainName, userName, userPassword,
                                 projectName,)
        '''
        payload = ''
        if self.scope == 'domain':
            payload = self.getPayloadWithDomainScope()
        else:
            payload = self.getPayloadWithProjectScope()

        payload  = json.dumps(payload)
        headers  = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        response = requests.post(self.tokenURL, headers=headers, data=payload)
        if not response.ok:
            elog.logging.error('failed to fetch token: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        return response.headers['X-Subject-Token']


class Roles(Token):
    def __init__(self):
        testConfig     = ConfigParser()
        cloudAdmin     = testConfig.getCloudAdmin()
        cloudAdminPass = testConfig.getCloudAdminPassword()
        super(Roles, self).__init__('domain', 'admin.local', cloudAdmin,
                                    cloudAdminPass)
        self.client    = RestClient(self.getToken())
        self.rolesURL  = self.keystoneURL + '/roles'

    def getRoles(self):
        response = self.client.get(self.rolesURL)
        if not response.ok:
            elog.logging.error('failed to get roles: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        return json.loads(response.content)

    def assignRole(self, domainID, userID, roleID):
        userURL    = '/users/' + userID
        roleURL    = '/roles/' + roleID
        domainURL  = '/domains/' + domainID
        requestURL = self.keystoneURL + domainURL + userURL + roleURL
        response   = self.client.put(requestURL)
        if not response.ok:
            elog.logging.error('failed to assign role %s to user %s in domain %s: %s'
                       % (eutil.bcolor(roleID), eutil.bcolor(userID),
                          eutil.bcolor(domainID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return False

        elog.logging.info('assigned role %s to user %s in domain %s'
                  % (eutil.bcolor(roleID), eutil.bcolor(userID),
                     eutil.bcolor(domainID)))
        return True


class Users(Token):
    def __init__(self):
        testConfig     = ConfigParser()
        cloudAdmin     = testConfig.getCloudAdmin()
        cloudAdminPass = testConfig.getCloudAdminPassword()
        super(Users, self).__init__('domain', 'admin.local', cloudAdmin,
                                    cloudAdminPass)
        self.client    = RestClient(self.getToken())
        self.usersURL  = self.keystoneURL + '/users'

    def createUser(self, domainID, userName, password):
        payload = {
            "user": {
                "name"     : userName,
                "email"    : "username@%s.com" % domainID,
                "enabled"  : True,
                "password" : password,
                "domain_id": domainID
            }
        }
        elog.logging.info('creating user %s' % eutil.bcolor(userName))
        response = self.client.post(self.usersURL, payload)
        if not response.ok:
            elog.logging.error('failed to create user: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        content = json.loads(response.content)
        userID  = content['user']['id']
        elog.logging.info('user %s created successfully: %s'
                  % (eutil.bcolor(userName),
                     eutil.bcolor(userID)))
        return userID

    def getURL(self, domainID):
        if not domainID:
            return self.usersURL

        return self.usersURL + '?domain_id=%s' % domainID

    def getUsers(self, domainID=''):
        requestURL = self.getURL(domainID)
        response   = self.client.get(requestURL)
        if not response.ok:
            elog.logging.error('failed to get users from domain %s: %s'
                       % (eutil.bcolor(domainID),
                          eutil.rcolor(response.status_code)))
            elog.logging.error(response.text)
            return None

        return json.loads(response.content)

    def deleteUser(self, userID):
        elog.logging.info('deleting user %s' % eutil.bcolor(userID))
        response = self.client.delete(self.domainURL+ '/' + userID)
        if not response.ok:
            elog.logging.error('failed to delete user: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return False

        elog.logging.info('deleting user %s: %s OK'
                  % (eutil.bcolor(userID),
                     eutil.gcolor(response.status_code)))
        return True


class Domains(Token):
    def __init__(self):
        testConfig     = ConfigParser()
        cloudAdmin     = testConfig.getCloudAdmin()
        cloudAdminPass = testConfig.getCloudAdminPassword()
        super(Domains, self).__init__('domain', 'admin.local', cloudAdmin,
                                      cloudAdminPass)
        self.client    = RestClient(self.getToken())
        self.domainURL = self.keystoneURL + '/domains'

    def createDomain(self, domainName, description = None, ldapset=False):
        payload = {
            "domain": {
                "name"        : domainName,
                "description" : description,
                "ldapSet"     : ldapset
            }
        }
        elog.logging.info('creating domain %s' % eutil.bcolor(domainName))
        response = self.client.post(self.domainURL, payload)
        if not response.ok:
            elog.logging.error('failed to create domain: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return None

        # while creating a new domain EB automatically assigns admin user
        # with admin role to the domain
        content  = json.loads(response.content)
        domainID = content['domain']['id']
        elog.logging.info('domain %s created successfully: %s'
                  % (eutil.bcolor(domainName),
                     eutil.bcolor(domainID)))
        return domainID

    def updateDomain(self, domainID, description = None, enabled=False):
        payload = {
            "domain": {
                "description" : description,
                "enabled"     : enabled
            }
        }
        elog.logging.info('Updating domain %s' % eutil.bcolor(domainID))
        response = self.client.patch(self.domainURL+ '/' + domainID, payload)
        if not response.ok:
            elog.logging.error('failed to update domain: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return False

        elog.logging.info('updating domain %s: %s OK'
                  % (eutil.bcolor(domainID),
                     eutil.gcolor(response.status_code)))
        return True

    def deleteDomain(self, domainID):
        elog.logging.info('deleting domain %s' % eutil.bcolor(domainID))
        response = self.client.delete(self.domainURL+ '/' + domainID)
        if not response.ok:
            elog.logging.error('failed to delete domain: %s'
                       % eutil.rcolor(response.status_code))
            elog.logging.error(response.text)
            return False

        elog.logging.info('deleting domain %s: %s OK'
                  % (eutil.bcolor(domainID),
                     eutil.gcolor(response.status_code)))
        return True
