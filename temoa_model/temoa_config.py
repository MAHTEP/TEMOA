"""
Tools for Energy Model Optimization and Analysis (Temoa):
An open source framework for energy systems optimization modeling

Copyright (C) 2015,  NC State University

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

A complete copy of the GNU General Public License v2 (GPLv2) is available
in LICENSE.txt.  Users uncompressing this from an archive may not have
received this license file.  If not, see <http://www.gnu.org/licenses/>.
"""
from os.path import abspath, isfile, splitext, dirname
from os import sep

import re

def db_2_dat(ifile, ofile, options):
	# Adapted from DB_to_DAT.py
	import sqlite3
	import sys
	import re
	import getopt

	def write_tech_mga(f):
		cur.execute("SELECT tech FROM tech_mga")
		f.write("set tech_mga :=\n")
		for row in cur:
			f.write(row[0] + '\n')
		f.write(';\n\n')

	def write_tech_sector(f):
		sectors = set()
		cur.execute("SELECT sector FROM technologies")
		for row in cur:
			sectors.add(row[0])
		for s in sectors:
			cur.execute("SELECT tech FROM technologies WHERE sector == '" + s + "'")
			f.write("set tech_" + s + " :=\n")
			for row in cur:
				f.write(row[0] + '\n')
			f.write(';\n\n')

	def query_table (t_properties, f):
		t_type = t_properties[0]   #table type (set or param)
		t_name = t_properties[1]   #table name
		t_dtname = t_properties[2] #DAT table name when DB table must be subdivided
		t_flag = t_properties[3]   #table flag, if any
		t_index = t_properties[4]  #table column index after which '#' should be specified
		if type(t_flag) is list:   #tech production table has a list for flags; this is currently hard-wired
			db_query = "SELECT * FROM " + t_name + " WHERE flag=='p' OR flag=='pb' OR flag=='ps'"
			cur.execute(db_query)
			if cur.fetchone() is None:
				return
			if t_type == "set":
				f.write("set " + t_dtname + " := \n")
			else:
				f.write("param " + t_dtname + " := \n")
		elif t_flag != '':    #check to see if flag is empty, if not use it to make table
			db_query = "SELECT * FROM " + t_name + " WHERE flag=='" + t_flag + "'"
			cur.execute(db_query)
			if cur.fetchone() is None:
				return
			if t_type == "set":
				f.write("set " + t_dtname + " := \n")
			else:
				f.write("param " + t_dtname + " := \n")
		else:    #Only other possible case is empty flag, then 1-to-1 correspodence between DB and DAT table names
			db_query = "SELECT * FROM " + t_name
			cur.execute(db_query)
			if cur.fetchone() is None:
				return
			if t_type == "set":
				f.write("set " + t_name + " := \n")
			else:
				f.write("param " + t_name + " := \n")
		cur.execute(db_query)
		if t_index == 0:    #make sure that units and descriptions are commented out in DAT file
			for line in cur:
				str_row = str(line[0]) + "\n"
				f.write(str_row)
				print(str_row)
		else:
			for line in cur:
				before_comments = line[:t_index+1]
				before_comments = re.sub('[(]', '', str(before_comments))
				before_comments = re.sub('[\',)]', '    ', str(before_comments))
				after_comments = line[t_index+2:]
				after_comments = re.sub('[(]', '', str(after_comments))
				after_comments = re.sub('[\',)]', '    ', str(after_comments))
				search_afcom = re.search(r'^\W+$', str(after_comments))		#Search if after_comments is empty.
				if not search_afcom :
					str_row = before_comments + "# " + after_comments + "\n"
				else :
						str_row = before_comments + "\n"
				f.write(str_row)
				print(str_row)
		f.write(';\n\n')

	#[set or param, table_name, DAT fieldname, flag (if any), index (where to insert '#')
	table_list = [
		['set',  'time_periods',						'time_exist',          'e',            0],
		['set',  'time_periods',						'time_future',         'f',            0],
		['set',  'time_season',               			'',                    '',             0],
		['set',  'time_of_day',               			'',                    '',             0],
		['set',  'regions',        	          			'',                    '',             0],
		['set',  'tech_curtailment',          			'',                    '',             0],
		['set',  'tech_flex',          		  			'',                    '',             0],
		['set',  'tech_reserve',              			'',                    '',             0],
		['set',  'technologies',              			'tech_resource',       'r',            0],
		['set',  'technologies',              			'tech_production',    ['p','pb','ps'], 0],
		['set',  'technologies',              			'tech_baseload',       'pb',           0],
		['set',  'technologies',              			'tech_storage',  	   'ps',           0],
		['set',  'tech_ramping',              			'',                    '',             0],
		['set',  'tech_exchange',             			'',                    '',             0],
		['set',  'tech_imports',              			'',                    '',             0],
		['set',  'tech_exports',              			'',                    '',             0],
		['set',  'tech_domestic',             			'',                    '',             0],
		['set',  'commodities',               			'commodity_physical',  'p',            0],
		['set',  'commodities',               			'commodity_material',  'm',            0],
		['set',  'commodities',               			'commodity_emissions', 'e',            0],
		['set',  'commodities',               			'commodity_demand',    'd',            0],
		['set',  'commodities_e_moo',                   '',                    '',             0],
		['set',  'tech_groups',               			'',                    '',             0],
		['set',  'tech_annual',               			'',                    '',             0],
		['set',  'tech_variable',             			'',                    '',             0],
		['set',  'groups',                    			'',                    '',             0],
		['param','TechGroupWeight',           			'',                    '',             2],
		['param','MinActivityGroup',          			'',                    '',             3],
		['param','MaxActivityGroup',          			'',                    '',             3],
		['param','MinCapacityGroup',          			'',                    '',             3],
		['param','MaxCapacityGroup',          			'',                    '',             3],
		['param','MinInputGroup',             			'',                    '',             4],
		['param','MaxInputGroup',             			'',                    '',             4],
		['param','MinOutputGroup',            			'',                    '',             4],
		['param','MaxOutputGroup',            			'',                    '',             4],
		['param','LinkedTechs',               			'',                    '',             3],
		['param','SegFrac',                   			'',                    '',             2],
		['param','DemandSpecificDistribution',			'',                    '',             4],
		['param','CapacityToActivity',        			'',                    '',             2],
		['param','PlanningReserveMargin',     			'',                    '',             2],
		['param','GlobalDiscountRate',        			'',                    '',             0],
		['param','MyopicBaseyear',            			'',                    '',             0],
		['param','DiscountRate',              			'',                    '',             3],
		['param','EmissionActivity',          			'',                    '',             6],
		['param','EmissionLimit',             			'',                    '',             3],
		['param','Demand',                    			'',                    '',             3],
		['param','TechOutputSplit',           			'',                    '',             4],
		['param','TechInputSplit',            			'',                    '',             4],
		['param','TechInputSplitAverage',     			'',                    '',             4],
		['param','MinCapacity',               			'',                    '',             3],
		['param','MaxCapacity',               			'',                    '',             3],
		['param','DiscreteCapacity',                    '',                    '',             1],
		['param','MaxActivity',               			'',                    '',             3],
		['param','MinActivity',               			'',                    '',             3],
		['param','MaxResource',               			'',                    '',             2],
		['param','GrowthRateMax',             			'',                    '',             2],
		['param','GrowthRateSeed',            			'',                    '',             2],
		['param','LifetimeTech',              			'',                    '',             2],
		['param','LifetimeProcess',           			'',                    '',             3],
		['param','LifetimeLoanTech',          			'',                    '',             2],
		['param','CapacityFactor',            			'',                    '',             3],
		['param','CapacityFactorTech',        			'',                    '',             4],
		['param','CapacityFactorProcess',     			'',                    '',             5],
		['param','Efficiency',                			'',                    '',             5],
		['param','ExistingCapacity',          			'',                    '',             3],
		['param','CostInvest',                			'',                    '',             3],
		['param','CostFixed',                 			'',                    '',             4],
		['param','CostVariable',              			'',                    '',             4],
		['param','CapacityCredit',            			'',                    '',             4],
		['param','RampUp',                    			'',                    '',             2],
		['param','RampDown',                  			'',                    '',             2],
		['param','StorageInitFrac',           			'',                    '',             3],
		['param','StorageDuration',           			'',                    '',             2],
		['param','MultiObjectiveSlacked',	            '',               	   '',             1],
		['param','EnergyCommodityConcentrationIndex',	'',               	   '',             3],
		['param','TechnologyMaterialSupplyRisk',		'',                    '',             3],
	    ['param','MaterialIntensity',         			'',                    '',             4],
	    ['param','MaxMaterialReserve',        			'',                    '',             2]]

	with open(ofile, 'w') as f:
		f.write('data ;\n\n')
		#connect to the database
		con = sqlite3.connect(ifile, isolation_level=None)
		cur = con.cursor()   # a database cursor is a control structure that enables traversal over the records in a database
		con.text_factory = str #this ensures data is explored with the correct UTF-8 encoding

		# Return the full list of existing tables.
		table_exist = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
		table_exist = [i[0] for i in table_exist]

		for table in table_list:
			if table[1] in table_exist:
				query_table(table, f)
		if options.mga_method == 'integer' or options.mga_method == 'random':
			write_tech_mga(f)
		if options.mga_method == 'normalized':
			write_tech_sector(f)
		if options.mgpa_method == 'integer' or options.mgpa_method == 'random':
			write_tech_mga(f)
		if options.mgpa_method == 'normalized':
			write_tech_sector(f)

		# Making sure the database is empty from the begining for a myopic solve
		if options.myopic:
			cur.execute("DELETE FROM Output_CapacityByPeriodAndTech WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_Emissions WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_Costs WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_Objective WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_VFlow_In WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_VFlow_Out WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_V_Capacity WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_Curtailment WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("DELETE FROM Output_Duals WHERE scenario="+"'"+str(options.scenario)+"'")
			cur.execute("VACUUM")
			con.commit()

		cur.close()
		con.close()

class TemoaConfig( object ):
	states = (
	('mga',  'exclusive'),
	('moo',  'exclusive'),
	('mgpa', 'exclusive'),
	)

	tokens = (
		'dot_dat',
		'output',
		'scenario',
		'how_to_cite',
		'version',
		'solver',
		'method',
		'threads',
		'tee',
		'neos',
		'keep_pyomo_lp_file',
		'saveEXCEL',
		'myopic'
		'myopic_periods'
		'keep_myopic_databases'
		'saveDUALS'
		'saveTEXTFILE',
		'path_to_data',
		'path_to_logs',
		'mgaslack',		# MGA slack
		'mgaiter',		# MGA iterations
		'mgaweight',	# MGA weighting method
		'moof1',		# MOO f1
		'moof2',		# MOO f2
		'mooc', 		# MOO c parameter
		'mooncaps',		# MOO number of caps,
		'mgpaf1', 		# MGPA f1
		'mgpaf2', 		# MGPA f2
		'mgpac', 		# MGPA c parameter
		'mgpancaps', 	# MGPA number of caps
		'mgpaslack1', 	# MGPA slack1
		'mgpaslack2', 	# MGPA slack2
		'mgpaiter', 	# MGPA iterations
		'mgpamethod' 	# MGPA weighting method
	)

	t_ANY_ignore  = '[ \t]'

	def __init__(self, **kwargs):
		# Make compatible with Python 2.7 and 3
		try:
			import queue
		except:
			import Queue as queue

		self.__error          = list()
		self.__mga_todo       = queue.Queue()  # MGA
		self.__mga_done       = queue.Queue()  # MGA
		self.__moo_todo       = queue.Queue()  # MOO
		self.__moo_done       = queue.Queue()  # MOO
		self.__mgpa_todo       = queue.Queue() # MGPA
		self.__mgpa_done       = queue.Queue() # MGPA

		self.file_location    = None
		self.dot_dat          = list() # Use Kevin's name.
		self.output           = None # May update to a list if multiple output is required.
		self.scenario         = None
		self.saveEXCEL        = False
		self.myopic           = False
		self.myopic_periods   = 0
		self.KeepMyopicDBs    = False
		self.saveDUALS     	  = False
		self.saveTEXTFILE     = False
		self.how_to_cite      = None
		self.version          = False
		self.neos             = False
		self.method           = None
		self.threads          = None
		self.tee       	      = False
		self.generateSolverLP = False
		self.keepPyomoLP      = False
		self.mga_slack        = None # MGA slack value
		self.mga_iter         = None # MGA iterations
		self.mga_method       = None # MGA weighting method
		self.moo_f1           = None # MOO f1
		self.moo_f2           = None # MOO f2
		self.moo_c            = None # MOO c parameter
		self.moo_ncaps        = None # MOO number of caps
		self.mgpa_f1          = None # MGPA f1
		self.mgpa_f2          = None # MGPA f2
		self.mgpa_c           = None # MGPA c parameter
		self.mgpa_ncaps       = None # MGPA number of caps
		self.mgpa_slack1      = None # MGPA slack value for f1
		self.mgpa_slack2      = None # MGPA slack value for f2
		self.mgpa_iter        = None # MGPA iterations
		self.mgpa_method      = None # MGPA weighting method

		# To keep consistent with Kevin's argumetn parser, will be removed in the future.
		self.graph_format     = None
		self.show_capacity    = False
		self.graph_type       = 'separate_vintages'
		self.use_splines      = False

		#Introduced during UI Development
		self.path_to_data    = re.sub('temoa_model$', 'data_files', dirname(abspath(__file__)))# Path to where automated excel and text log folder will be save as output.
		self.path_to_logs     = self.path_to_data+sep+"debug_logs" #Path to where debug logs will be generated for each run. By default in debug_logs folder in db_io.
		self.path_to_lp_files = None
		self.abort_temoa	  = False

		if 'd_solver' in kwargs.keys():
			self.solver = kwargs['d_solver']
		else:
			self.solver = None

	def __repr__(self):
		width = 30
		spacer = '-'*width + '\n'
		msg = spacer
		msg += '{:>{}s}: {}\n'.format('Config file', width, self.file_location)
		for i in self.dot_dat:
			if self.dot_dat.index(i) == 0:
				msg += '{:>{}s}: {}\n'.format('Input file', width, i)
			else:
				msg += '{:>25s}  {}\n'.format(' ', i)
		msg += '{:>{}s}: {}\n'.format('Output file', width, self.output)
		msg += '{:>{}s}: {}\n'.format('Scenario', width, self.scenario)
		msg += '{:>{}s}: {}\n'.format('Spreadsheet output', width, self.saveEXCEL)
		msg += '{:>{}s}: {}\n'.format('Myopic scheme', width, self.myopic)
		msg += '{:>{}s}: {}\n'.format('Myopic years', width, self.myopic_periods)
		msg += '{:>{}s}: {}\n'.format('Retain myopic databases', width, self.KeepMyopicDBs)
		msg += spacer
		msg += '{:>{}s}: {}\n'.format('Citation output status', width, self.how_to_cite)
		msg += '{:>{}s}: {}\n'.format('NEOS status', width, self.neos)
		msg += '{:>{}s}: {}\n'.format('Version output status', width, self.version)
		msg += spacer
		msg += '{:>{}s}: {}\n'.format('Selected solver', width, self.solver)
		msg += '{:>{}s}: {}\n'.format('Selected optimization method', width, self.method)
		msg += '{:>{}s}: {}\n'.format('Selected number of threads', width, self.threads)
		msg += '{:>{}s}: {}\n'.format('Solver outputs status', width, self.tee)
		msg += '{:>{}s}: {}\n'.format('Solver LP write status', width, self.generateSolverLP)
		msg += '{:>{}s}: {}\n'.format('Pyomo LP write status', width, self.keepPyomoLP)
		if self.mga_slack != None:
			msg += spacer
			msg += '{:>{}s}: {}\n'.format('MGA slack value', width, self.mga_slack)
			msg += '{:>{}s}: {}\n'.format('MGA # of iterations', width, self.mga_iter)
			msg += '{:>{}s}: {}\n'.format('MGA weighting method', width, self.mga_method)
		if self.moo_c != None:
			msg += spacer
			msg += '{:>{}s}: {}\n'.format('MOO f1', width, self.moo_f1)
			msg += '{:>{}s}: {}\n'.format('MOO f2', width, self.moo_f2)
			msg += '{:>{}s}: {}\n'.format('MOO c parameter', width, self.moo_c)
			msg += '{:>{}s}: {}\n'.format('MOO # of caps', width, self.moo_ncaps)
		if self.mgpa_c != None:
			msg += spacer
			msg += '{:>{}s}: {}\n'.format('MGPA f1', width, self.mgpa_f1)
			msg += '{:>{}s}: {}\n'.format('MGPA f2', width, self.mgpa_f2)
			msg += '{:>{}s}: {}\n'.format('MGPA c parameter', width, self.mgpa_c)
			msg += '{:>{}s}: {}\n'.format('MGPA # of caps', width, self.mgpa_ncaps)
			msg += '{:>{}s}: {}\n'.format('MGPA slack1 value', width, self.mgpa_slack1)
			msg += '{:>{}s}: {}\n'.format('MGPA slack2 value', width, self.mgpa_slack2)
			msg += '{:>{}s}: {}\n'.format('MGPA # of iterations', width, self.mgpa_iter)
			msg += '{:>{}s}: {}\n'.format('MGPA weighting method', width, self.mgpa_method)
		msg += spacer
		return msg

	def t_ANY_COMMENT(self, t):
		r'\#.*'
		pass

	def t_dot_dat(self, t):
		r'--input[\s\=]+[-\\\/\:\.\~\w]+(\.dat|\.db|\.sqlite)\b'
		self.dot_dat.append(abspath(t.value.replace('=', ' ').split()[1]))

	def t_output(self, t):
		r'--output[\s\=]+[-\\\/\:\.\~\w]+(\.db|\.sqlite)\b'
		self.output = abspath(t.value.replace('=', ' ').split()[1])

	def t_scenario(self, t):
		r'--scenario[\s\=]+\w+\b'
		self.scenario = t.value.replace('=', ' ').split()[1]

	def t_saveEXCEL(self, t):
		r'--saveEXCEL\b'
		self.saveEXCEL = True

	def t_saveDUALS(self, t):
		r'--saveDUALS\b'
		self.saveDUALS = True

	def t_myopic(self, t):
		r'--myopic\b'
		self.myopic = True

	def t_myopic_periods(self, t):
		r'--myopic_periods[\s\=]+[\d]+'
		self.myopic_periods = int(t.value.replace('=', ' ').split()[1])

	def t_keep_myopic_databases(self, t):
		r'--keep_myopic_databases\b'
		self.KeepMyopicDBs = True

	def t_saveTEXTFILE(self, t):
		r'--saveTEXTFILE\b'
		self.saveTEXTFILE = True

	def t_path_to_data(self, t):
		r'--path_to_data[\s\=]+[-\\\/\:\.\~\w\ ]+\b'
		self.path_to_data = abspath(t.value.replace('=', ',').split(",")[1])

	def t_path_to_logs(self, t):
		r'--path_to_logs[\s\=]+[-\\\/\:\.\~\w\ ]+\b'
		self.path_to_logs = abspath(t.value.replace('=', ',').split(",")[1])

	def t_how_to_cite(self, t):
		r'--how_to_cite\b'
		self.how_to_cite = True

	def t_version(self, t):
		r'--version\b'
		self.version = True

	def t_neos(self, t):
		r'--neos\b'
		self.neos = True

	def t_solver(self, t):
		r'--solver[\s\=]+\w+\b'
		self.solver = t.value.replace('=', ' ').split()[1]

	def t_method(self, t):
		r'--method[\s\=]+\w+\b'
		self.method = t.value.replace('=', ' ').split()[1]

	def t_threads(self, t):
		r'--threads[\s\=]+\w+\b'
		self.threads = t.value.replace('=', ' ').split()[1]

	def t_tee(self, t):
		r'--tee\b'
		self.tee = True

	def t_keep_pyomo_lp_file(self, t):
		r'--keep_pyomo_lp_file\b'
		self.keepPyomoLP = True

	def t_begin_mga(self, t):
		r'--mga[\s\=]+\{'
		t.lexer.push_state('mga')
		t.lexer.level = 1

	def t_mga_mgaslack(self, t):
		r'slack[\s\=]+[\.\d]+'
		self.mga_slack = float(t.value.replace('=', ' ').split()[1])

	def t_mga_mgaiter(self, t):
		r'iteration[\s\=]+[\d]+'
		self.mga_iter = int(t.value.replace('=', ' ').split()[1])

	def t_mga_mgamethod(self, t):
		r'method[\s\=]+(integer|normalized|random)\b'
		self.mga_method = t.value.replace('=', ' ').split()[1]

	def t_mga_end(self, t):
		r'\}'
		t.lexer.pop_state()
		t.lexer.level -= 1

	def t_begin_moo(self, t): #MOO begin
		r'--moo[\s\=]+\{'
		t.lexer.push_state('moo')
		t.lexer.level = 1

	def t_moo_moof1(self, t): #MOO f1
		r'f1[\s\=]+(cost|emissions|energySR|materialSR)\b'
		self.moo_f1 = t.value.replace('=', ' ').split()[1]

	def t_moo_moof2(self, t): #MOO f2
		r'f2[\s\=]+(cost|emissions|energySR|materialSR)\b'
		self.moo_f2 = t.value.replace('=', ' ').split()[1]

	def t_moo_mooc(self, t): #MOO c parameter
		r'c[\s\=]+[\.\d]+'
		self.moo_c = float(t.value.replace('=', ' ').split()[1])

	def t_moo_mooncaps(self, t): #MOO number of caps
		r'ncaps[\s\=]+[\d]+'
		self.moo_ncaps = int(t.value.replace('=', ' ').split()[1])

	def t_moo_end(self, t): #MOO end
		r'\}'
		t.lexer.pop_state()
		t.lexer.level -= 1

	def t_begin_mgpa(self, t): #MGPA begin
		r'--mgpa[\s\=]+\{'
		t.lexer.push_state('mgpa')
		t.lexer.level = 1

	def t_mgpa_mgpaf1(self, t): #MGPA f1
		r'f1[\s\=]+(cost|emissions|energySR|materialSR)\b'
		self.mgpa_f1 = t.value.replace('=', ' ').split()[1]

	def t_mgpa_mgpaf2(self, t): #MGPA f2
		r'f2[\s\=]+(cost|emissions|energySR|materialSR)\b'
		self.mgpa_f2 = t.value.replace('=', ' ').split()[1]

	def t_mgpa_mgpac(self, t): #MGPA c parameter
		r'c[\s\=]+[\.\d]+'
		self.mgpa_c = float(t.value.replace('=', ' ').split()[1])

	def t_mgpa_mgpancaps(self, t): #MGPA number of caps
		r'ncaps[\s\=]+[\d]+'
		self.mgpa_ncaps = int(t.value.replace('=', ' ').split()[1])

	def t_mgpa_mgpaslack1(self, t): #MGPA slack1
		r'slack1[\s\=]+[\.\d]+'
		self.mgpa_slack1 = float(t.value.replace('=', ' ').split()[1])

	def t_mgpa_mgpaslack2(self, t): #MGPA slack2
		r'slack2[\s\=]+[\.\d]+'
		self.mgpa_slack2 = float(t.value.replace('=', ' ').split()[1])

	def t_mgpa_mgpaiter(self, t): #MGPA iterations
		r'iteration[\s\=]+[\d]+'
		self.mgpa_iter = int(t.value.replace('=', ' ').split()[1])

	def t_mgpa_mgpamethod(self, t): #MGPA weighting method
		r'method[\s\=]+(integer|normalized|random)\b'
		self.mgpa_method = t.value.replace('=', ' ').split()[1]

	def t_mgpa_end(self, t): #MGPA end
		r'\}'
		t.lexer.pop_state()
		t.lexer.level -= 1

	def t_ANY_newline(self,t):
		r'\n+|(\r\n)+|\r+' # '\n' (In linux) = '\r\n' (In Windows) = '\r' (In Mac OS)
		t.lexer.lineno += len(t.value)

	def t_ANY_error(self, t):
		if not self.__error:
			self.__error.append({'line': [t.lineno, t.lineno], 'index': [t.lexpos, t.lexpos], 'value': t.value[0]})
		elif t.lexpos - self.__error[-1]['index'][-1] == 1:
			self.__error[-1]['line' ][-1] = t.lineno
			self.__error[-1]['index'][-1] = t.lexpos
			self.__error[-1]['value'] += t.value[0]
		else:
			self.__error.append({'line': [t.lineno, t.lineno], 'index': [t.lexpos, t.lexpos], 'value': t.value[0]})
		t.lexer.skip(1)

	def next_mga(self):
		if not self.__mga_todo.empty():
			self.__mga_done.put(self.scenario)
			self.scenario = self.__mga_todo.get()
			return True
		else:
			return False

	def next_moo(self): #MOO
		if not self.__moo_todo.empty(): # If todo is not empty
			self.__moo_done.put(self.scenario) # Put the current scenario to done
			self.scenario = self.__moo_todo.get() # Assign the next todo scenario to scenario (in config_sample)
			return True
		else: # If there are no further scenarios to process
			return False

	def next_mgpa(self): #MGPA
		if not self.__mgpa_todo.empty(): # If todo is not empty
			self.__mgpa_done.put(self.scenario) # Put the current scenario to done
			self.scenario = self.__mgpa_todo.get() # Assign the next todo scenario to scenario (in config_sample)
			return True
		else: # If there are no further scenarios to process
			return False

	def build(self,**kwargs):
		import ply.lex as lex, os, sys

		db_or_dat = True # True means input file is a db file. False means input is a dat file.

		if 'config' in kwargs:
			if isfile(kwargs['config']):
				self.file_location= abspath(kwargs.pop('config'))
			else:
				msg = 'No such file exists: {}'.format(kwargs.pop('config'))
				raise Exception( msg )

		self.lexer = lex.lex(module=self, **kwargs)
		if self.file_location:
			try:
				with open(self.file_location, encoding="utf8") as f:
					self.lexer.input(f.read())
			except:
				with open(self.file_location, 'r') as f:
					self.lexer.input(f.read())
			while True:
				tok = self.lexer.token()
				if not tok: break

		if self.__error:
			width = 25
			msg = '\nIllegal character(s) in config file:\n'
			msg += '-'*width + '\n'
			for e in self.__error:
				msg += "Line {} to {}: '{}'\n".format(e['line'][0], e['line'][1], e['value'])
			msg += '-'*width + '\n'
			sys.stderr.write(msg)

			try:
				txt_file = open(self.path_to_logs+os.sep+"Complete_OutputLog.log", "w")
			except BaseException as io_exc:
				sys.stderr.write("Log file cannot be opened. Please check path. Trying to find:\n"+self.path_to_logs+" folder\n")
				txt_file = open("OutputLog.log", "w")

			txt_file.write( msg )
			txt_file.close()
			self.abort_temoa = True


		if not self.dot_dat:
			raise Exception('Input file not specified.')

		for i in self.dot_dat:
			if not isfile(i):
				raise Exception('Cannot locate input file: {}'.format(i))
			i_name, i_ext = splitext(i)
			if (i_ext == '.dat') or (i_ext == '.txt'):
				db_or_dat = False
			elif (i_ext == '.db') or (i_ext == '.sqlite') or (i_ext == '.sqlite3') or (i_ext == 'sqlitedb'):
				db_or_dat = True

		if not self.output and db_or_dat:
			raise Exception('Output file not specified.')

		if db_or_dat and not isfile(self.output):
			raise Exception('Cannot locate output file: {}.'.format(self.output))

		if not self.scenario and db_or_dat:
			raise Exception('Scenario name not specified.')

		if self.mga_iter:
			for i in range(self.mga_iter):
				self.__mga_todo.put(self.scenario + '_mga_' + str(i))

		if self.moo_ncaps: #MOO if moo_ncaps is not zero
			for i in range(self.moo_ncaps):
				self.__moo_todo.put(self.scenario + '_moo_' + str(i)) # Populate todo with scenarios

		if self.mgpa_ncaps: #MGPA if mgpa_ncaps is not zero
			for i in range(self.mgpa_ncaps):
				self.__mgpa_todo.put(self.scenario + '_moo_' + str(i)) # Populate todo with scenarios
				if self.mgpa_iter:
					for j in range(self.mgpa_iter):
						self.__mgpa_todo.put(self.scenario + '_moo_' + str(i) + '_mga_' + str(j)) # Populate todo with scenarios

		f = open(os.devnull, 'w');
		sys.stdout = f # Suppress the original DB_to_DAT.py output

		counter = 0

		for ifile in self.dot_dat:
			i_name, i_ext = splitext(ifile)
			if i_ext != '.dat':
				ofile = i_name + '.dat'
				db_2_dat(ifile, ofile, self)
				self.dot_dat[self.dot_dat.index(ifile)] = ofile
				counter += 1
		f.close()
		sys.stdout = sys.__stdout__
		if counter > 0:
			sys.stderr.write("\n{} .db DD file(s) converted\n\n".format(counter))