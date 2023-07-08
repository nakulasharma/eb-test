#! /usr/bin/env python
#
# Author: vikram@edgebricks.com
# (c) 2021 Edgebricks Inc


from framework.base.baseActions import BaseActions
from framework.utilities.util import Util


class BasePage(BaseActions):
    """
    Class that contains methods common to all the pages
    """

    def __init__(self, driver):
        super(BasePage, self).__init__(driver)
        self.driver = driver
        self.util = Util()

    def verifyPageTitle(self, titleToVerify):
        """
        Verify the page title
        Parameters:
        titleToVerify : Title on the page that needs to be verified
        """
        try:
            actualTitle = self.getTitle()  # getTitle method of BaseTest class
            return self.util.verifyTextContains(actualTitle, titleToVerify)
        except BaseException:
            self.log.error("Failed to get Page Title")
            return False
