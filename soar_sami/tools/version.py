# -*- coding: utf-8 -*-
"""
v0.0.0 - Initial Version.
v0.1.0 - Pipeline actually running.
       - To Do: Improve LaCosmic parameters.
v0.1.1 - Fixed bug related to master bias and flat names.
       - Added prefix to reduced data.
v0.1.2 - Fixed bug related to the logging system.
"""

api = 0
feature = 1
bug = 2

month = 6
year = 2018

__str__ = "{api:d}.{feature:d}.{bug:d} {month:d}, {year:d}".format(**locals())
