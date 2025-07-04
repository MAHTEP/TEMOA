import sys
import os
import multiprocessing
import shutil

processes = 1
series = 1
files = []

def run(args):
    input_file, serie = args
    
    if serie == -1:
        output_file = input_file
    else:
        output_file = input_file[0:-7] + '_' + str(serie) + '.sqlite'
        shutil.copy('data_files/' + input_file, 'data_files/' + output_file)
    
    shutil.copy('temoa_model/config_sample', 'temoa_model/config_sample_' + input_file[0:-7] + '_' + str(serie))

    with open('temoa_model/config_sample_' + input_file[0:-7] + '_' + str(serie), "r") as file:
        lines = file.readlines()
    
    input_line = '--input=data_files/' + output_file + '\n'
    lines = [input_line if line.startswith('--input=') else line for line in lines]
    output_line = '--output=data_files/' + output_file + '\n'
    lines = [output_line if line.startswith('--output=') else line for line in lines]
    
    with open('temoa_model/config_sample_' + input_file[0:-7] + '_' + str(serie), "w") as file:
        file.writelines(lines)

    os.system('python temoa_model --config=temoa_model/config_sample_' + input_file[0:-7] + '_' + str(serie))
    os.remove('temoa_model/config_sample_' + input_file[0:-7] + '_' + str(serie))

input_file_list = []
serie_list = []

for f in files:
    if series == 1:
        input_file_list.append(f)
        serie_list.append(-1)
    else:
        for s in range(0,series):
            input_file_list.append(f)
            serie_list.append(s)

if __name__ ==  '__main__':
    inputs = list(zip(input_file_list, serie_list))

    with multiprocessing.Pool(processes=processes) as pool:
        results = pool.map(run, inputs)