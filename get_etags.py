from json import load
from json import dump
from json.decoder import JSONDecodeError

def main():
    output = {}
    try:
        with open('etags', 'r') as infile:
            output = load(infile)
    except JSONDecodeError:
        print('JSON decoder error in etags file; clearing file.')
        with open('etags', 'w') as outfile:
            dump(output, outfile)
    return output

if __name__ == '__main__':
    main()
