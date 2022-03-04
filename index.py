#!/usr/bin/python3
import nltk
import sys
import getopt
import json
import math
import pickle

from pathlib import Path
from string import punctuation

def usage():
    print("usage: " + sys.argv[0] + " -i directory-of-documents -d dictionary-file -p postings-file")

def build_index(in_dir, out_dict, out_postings):
    """
    build index from documents stored in the input directory,
    then output the dictionary file and postings file
    """
    print('indexing...')

    MEM_LIMIT = 100000 # Number of pairings
    HALF_LIMIT = MEM_LIMIT / 2
    STRING_MAX = '}' # Max string value as compared to dictionary terms
    mem = 0
    stemmer = nltk.PorterStemmer()
    dictionary = {}
    block_count = 0
    population = [] # Universal set

    for file in Path(in_dir).iterdir():
        population.append(int(file.name))
        with open(file) as doc:
            token_set = set() # Set is used to prevent duplicates
            tokens = nltk.word_tokenize(doc.read().lower()) # Tokenization and case folding

            # Stemming and punctuation stripping
            for tok in tokens:
                token_set.add(stemmer.stem(tok).strip(punctuation))

            # Removes the empty string from set - side effect of punctuation stripping
            if '' in token_set:
                token_set.remove('')

            mem += len(token_set) # Keeps track of 'memory'

            for tok in token_set:
                if tok in dictionary:
                    posting = dictionary[tok]
                    posting[0] += 1
                    posting[1].append(int(file.name))
                else:
                    dictionary[tok] = [1, [int(file.name)]]

            if mem > MEM_LIMIT:
                write_out(dictionary, block_count)
                block_count += 1
                mem = 0

    # Writes out any remaining dictionary items
    if len(dictionary) > 0:
        write_out(dictionary, block_count)
        block_count += 1

    files  = list(Path('.').glob('block*.txt'))
    terms = [] # Terms to be processed
    currs = [0] * block_count # File pointers
    final_dict = {}

    # Continuously reads chunks from blocks, merges and writes them out until all blocks have been fully read
    while len(files) > 0:
        lowest = read_chunks(files, currs, STRING_MAX, HALF_LIMIT, terms)
        merge_chunks(terms, dictionary)
        write_postings(out_postings, dictionary, lowest, final_dict)

    # Writes out the universal set and any remaining items
    dictionary['ALL'] = [len(population), population]
    write_postings(out_postings, dictionary, STRING_MAX, final_dict)

    # Writes out the final dictionary
    with open(out_dict, 'wb') as out_d:
        pickle.dump(final_dict, out_d)


# Writes out the filled dictionary onto the disk
def write_out(dictionary, block_count):
    sorted_dict = dict(sorted(dictionary.items()))

    with open('block' + str(block_count) + '.txt', 'w') as block_file:
        for item in sorted_dict.items():
            block_file.write(json.dumps(item) + '\n')

    dictionary.clear()


# Reads chunks from each block and stores them for later processing
def read_chunks(files, currs, string_max, half_limit, terms):
    lowest = string_max
    block_limit = half_limit / len(files) # Size limit for each block

    for i in reversed(range(len(files))):
        end = False
        with open(files[i]) as block:
            chunk_size = 0 # Keeps track of acquired chunk size
            block.seek(currs[i])
            line = block.readline()

            while line:
                term = json.loads(line)
                terms.append(term)
                chunk_size += term[1][0]

                # When the limit is reached, the current file position is recorded to allow later readings
                if chunk_size > block_limit:
                    currs[i] = block.tell()
                    if term[0] < lowest: # Records the smallest string among the chunks drawn this round
                        lowest = term[0]
                    break

                line = block.readline()

            # Checks if a block has reached the end
            if block.readline() == '':
                end = True
                
        if end:
            Path(files[i]).unlink()
            del files[i]
            del currs[i]

    return lowest


# Merges chunks into the main dictionary
def merge_chunks(terms, dictionary):
    for term in terms:
        if term[0] in dictionary:
            item = dictionary[term[0]]
            item[0] += term[1][0]
            item[1] += term[1][1]
        else:
            dictionary[term[0]] = term[1]

    terms.clear()


# Writes out the postings list of terms that have been merged from all blocks
def write_postings(out_postings, dictionary, lowest, final_dict):
    with open(out_postings, 'ab') as out_p:
        for k in list(dictionary.keys()):
            # If the term is smaller than the smallest last term read from all the blocks it has completed processing
            if k <= lowest:
                v = dictionary.pop(k)
                v[1].sort() # Sorts final posting list
                add_skips(v[1])
                final_dict[k] = (v[0], out_p.tell())
                pickle.dump(v[1], out_p)


# Adds skip pointers to the final postings lists
def add_skips(posting):
    posting_len = len(posting)

    if posting_len > 3:
        skip_len = math.floor(math.sqrt(posting_len))
        skip = 0
        for i in range(posting_len):
            if i == skip and (skip + skip_len) < posting_len:
                skip += skip_len
                posting[i] = (posting[i], skip)
            else:
                posting[i] = (posting[i], )
    else:
        for i in range(posting_len):
            posting[i] = (posting[i], )


input_directory = output_file_dictionary = output_file_postings = None

try:
    opts, args = getopt.getopt(sys.argv[1:], 'i:d:p:')
except getopt.GetoptError:
    usage()
    sys.exit(2)

for o, a in opts:
    if o == '-i': # input directory
        input_directory = a
    elif o == '-d': # dictionary file
        output_file_dictionary = a
    elif o == '-p': # postings file
        output_file_postings = a
    else:
        assert False, "unhandled option"

if input_directory == None or output_file_postings == None or output_file_dictionary == None:
    usage()
    sys.exit(2)

build_index(input_directory, output_file_dictionary, output_file_postings)
