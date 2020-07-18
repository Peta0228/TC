from time import sleep
import sys
import os

if len(sys.argv) == 1:
    print('did not provide a file path...')
    exit(1)

while True:
    count = 0  # number of executions
    interval = 600  # interval(seconds) to run file
    file_path = sys.argv[1]  # .py file to run

    print('run: #' + str(count))
    os.system('python3 ' + file_path)
    print('----------------------------------------------')
    count+=1
    sleep(interval)
