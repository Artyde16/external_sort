from random import randint

LINES = 10**4


with open(f'testing/t{randint(0,125)}.txt', 'w') as file:
    data = []
    for i in range(0,LINES):
        data.append(str(randint(0,LINES)) + '\n')
    file.writelines(data)