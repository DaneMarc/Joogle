#!/usr/bin/python3
import nltk
import sys
import getopt
import math
import pickle

from string import punctuation
from operator import itemgetter

OPEN = '('
CLOSE = ')'
AND = 'AND'
OR = 'OR'
NOT = 'NOT'

ops = { OPEN, CLOSE, AND, OR, NOT }

def usage():
    print("usage: " + sys.argv[0] + " -d dictionary-file -p postings-file -q file-of-queries -o output-file-of-results")

def run_search(dict_file, postings_file, queries_file, results_file):
    """
    using the given dictionary file and postings file,
    perform searching on the given queries file and output the results to a file
    """
    print('running search on the queries...')

    stemmer = nltk.PorterStemmer()
    op_stack = []       # Operator stack
    term_stack = []     # Term stack
    results = []        # Query results
    population = []     # List of all docs (universal set)

    with open(dict_file, 'rb') as d_file:
        dictionary = pickle.load(d_file)

    # Splits and prepares the queries for evaluation
    queries = []
    with open(queries_file, 'r') as q_file:
        for query in q_file:
            tokens = []
            for tok in query.split():
                if tok[0] == OPEN:
                    tokens.append(OPEN)
                    tokens.append(tok[1:])
                elif tok[-1] == CLOSE:
                    tokens.append(tok[:-1])
                    tokens.append(CLOSE)
                else:
                    tokens.append(tok)
            queries.append(tokens)


    with open(postings_file, 'rb') as postings:
        postings.seek(dictionary['ALL'][1])
        population = pickle.load(postings) # Sets universal set

        for query in queries:
            for tok in query:
                if tok in ops: # Checks if its an operator
                    if tok == CLOSE:
                        # Evaluates the queries in the parentheses
                        and_eval(op_stack, term_stack)
                        or_eval(op_stack, term_stack)

                        # Removes the open parenthesis
                        if not_empty(op_stack) and op_stack[-1] == OPEN:
                            op_stack.pop()

                        # Reverses result of parenthesis query if NOT found before ()
                        if not_empty(op_stack) and not_empty(term_stack) and op_stack[-1] == NOT:
                            term = term_stack.pop()
                            term_stack.append((1 if term[0] == 0 else 0, term[1], term[2]))
                            op_stack.pop()
                    elif tok == OR:
                        # Evaluates if it is preceded by AND operators
                        and_eval(op_stack, term_stack)
                        op_stack.append(tok)
                    elif tok == NOT and not_empty(op_stack) and op_stack[-1] == NOT: # Removes chained NOTs
                        op_stack.pop()
                    else:
                        op_stack.append(tok)
                else:
                    posting = []
                    freq = 0
                    tok = stemmer.stem(tok.lower()).strip(punctuation)

                    if tok in dictionary:
                        item = dictionary[tok]
                        postings.seek(item[1])
                        posting = pickle.load(postings)
                        freq = item[0]

                    # Checks if the term has a NOT operator and sets the NOT flag
                    if not_empty(op_stack) and op_stack[-1] == NOT:
                        term_stack.append((1, posting, freq)) # 1 if NOT, 0 if not NOT
                        op_stack.pop()
                    else:
                        term_stack.append((0, posting, freq))

            # Applies the remaining operators
            and_eval(op_stack, term_stack)
            or_eval(op_stack, term_stack)

            # Checks if the query is valid and then appends the result
            if len(op_stack) == 0 and len(term_stack) == 1:
                res = term_stack.pop()

                # Checks if the final result is a NOT term evaluates accordingly
                if res[0] == 0:
                    results.append(res[1])
                else:
                    results.append(subtract(population, res[1]))
            else:
                results.append([])
                op_stack.clear()
                term_stack.clear()

    with open(results_file, 'w') as r_file:
        for result in results:
            r_file.write(' '.join([str(x[0]) for x in result]) + '\n')


# Evaluates chain of AND queries
def and_eval(op_stack, term_stack):
    if not_empty(op_stack) and op_stack[-1] == AND:
        and_optimizer(op_stack, term_stack)
        while not_empty(op_stack) and op_stack[-1] == AND:
            apply_operators(op_stack, term_stack)


# Evaluates chain of OR queries
def or_eval(op_stack, term_stack):
    if not_empty(op_stack) and op_stack[-1] == OR:
        or_optimizer(op_stack, term_stack)
        while not_empty(op_stack) and op_stack[-1] == OR:
            apply_operators(op_stack, term_stack)


# Optimizes a chain of AND queries
def and_optimizer(op_stack, term_stack):
    count = 0

    # Counts the number of chained AND operators to determine the number of terms to pop
    for op in reversed(op_stack):
        if op == AND:
            count += 1
        else:
            break

    # Optimizes if there are at least 7 AND operators
    if count > 6 and len(term_stack) > count:
        and_terms = [] # Normal terms
        and_not_terms = [] # NOT terms

        for i in range(count + 1):
            term = term_stack.pop()
            if term[0] == 0:
                and_terms.append(term)
            else:
                and_not_terms.append(term)

        # Sorts normal terms based on doc frequency
        and_terms = sorted(and_terms, key=itemgetter(2), reverse=True)

        # Pushes normal terms onto the stack in descending order based on doc frequency
        for term in and_terms:
            term_stack.append(term)

        # Pushes NOT terms on top of the normal terms to be evaluated first
        for term in and_not_terms:
            term_stack.append(term)


# Optimizes a chain of OR queries
def or_optimizer(op_stack, term_stack):
    count = 0

    for op in reversed(op_stack):
        if op == OR:
            count += 1
        else:
            break

    if count > 3 and len(term_stack) > count:
        or_terms = []
        or_not_terms = []

        for i in range(count + 1):
            term = term_stack.pop()
            if term[0] == 0:
                or_terms.append(term)
            else:
                or_not_terms.append(term)

        or_not_terms = sorted(or_not_terms, key=itemgetter(2), reverse=True)

        for term in or_terms:
            term_stack.append(term)

        for term in or_not_terms:
            term_stack.append(term)


# Applies an operator to two terms
def apply_operators(op_stack, term_stack):
    if len(term_stack) >= 2:
        op = op_stack.pop()
        right = term_stack.pop()
        left = term_stack.pop()

        if op == AND:
            if left[0] == 0 and right[0] == 0:              # left AND right
                intermediate = intersect(left[1], right[1])
                term_stack.append((0, intermediate, len(intermediate)))
            elif left[0] == 0 and right[0] == 1:            # left AND NOT right
                intermediate = subtract(left[1], right[1])  # Simplified to left - right
                term_stack.append((0, intermediate, len(intermediate)))
            elif left[0] == 1 and right[0] == 0:            # NOT left AND right
                intermediate = subtract(right[1], left[1])  # Simplified to right - left
                term_stack.append((0, intermediate, len(intermediate)))
            else:                                           # NOT left AND NOT right
                intermediate = union(left[1], right[1])     # Simplified to NOT (left + right)
                term_stack.append((1, intermediate, len(intermediate)))
        elif op == OR:
            if left[0] == 0 and right[0] == 0:              # left OR right
                intermediate = union(left[1], right[1])
                term_stack.append((0, intermediate, len(intermediate)))
            elif left[0] == 0 and right[0] == 1:            # left OR NOT right
                intermediate = subtract(right[1], left[1])  # Simplified to NOT (right - left)
                term_stack.append((1, intermediate, len(intermediate)))
            elif left[0] == 1 and right[0] == 0:            # NOT left OR right
                intermediate = subtract(left[1], right[1])  # Simplified to NOT (left - right)
                term_stack.append((1, intermediate, len(intermediate)))
            else:                                           # NOT left or NOT right
                intermediate = intersect(left[1], right[1]) # Simplified to NOT (left . right)
                term_stack.append((1, intermediate, len(intermediate)))
        else:
            # Clears stacks if query is invalid
            op_stack.clear()
            term_stack.clear()
    else:
        op_stack.clear()
        term_stack.clear()


# Formats integer arrays and adds skip pointers
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


def not_empty(stack):
    return len(stack) > 0


# Gets the intersection of two posting lists (AND operation)
def intersect(left, right):
    i = j = 0
    arr = []

    while i < len(left) and j < len(right):
        a = left[i][0]
        b = right[j][0]

        if a == b:
            arr.append(a)
            i += 1
            j += 1
        elif a < b:
            # Checks if a skip pointer is available and if the jump doesn't overshoot
            if len(left[i]) == 2 and left[left[i][1]][0] <= b:
                i = left[i][1]
            else:
                i += 1
        else:
            if len(right[j]) == 2 and right[right[j][1]][0] <= a:
                j = right[j][1]
            else:
                j += 1

    # Formats the resulting intermediate list and adds skip pointers
    add_skips(arr)
    return arr


# Joins two posting lists (OR operation)
def union(left, right):
    i = j = 0
    arr = []

    while i < len(left) and j < len(right):
        a = left[i][0]
        b = right[j][0]

        if a == b:
            arr.append(a)
            i += 1
            j += 1
        elif a < b:
            arr.append(a)
            i += 1
        else:
            arr.append(b)
            j += 1

    while i < len(left):
        arr.append(left[i][0])
        i += 1

    while j < len(right):
        arr.append(right[j][0])
        j += 1

    add_skips(arr)
    return arr


# Removes elements in the right list from the left list
# Used instead of AND NOT
def subtract(left, right):
    i = j = 0
    arr = []

    while i < len(left) and j < len(right):
        a = left[i][0]
        b = right[j][0]

        if a == b:
            i += 1
            j += 1
        elif a < b:
            arr.append(a)
            if len(left[i]) == 2 and left[left[i][1]][0] <= b:
                i = left[i][1]
            else:
                i += 1
        else:
            if len(right[j]) == 2 and right[right[j][1]][0] <= a:
                j = right[j][1]
            else:
                j += 1

    while i < len(left):
        arr.append(left[i][0])
        i += 1

    add_skips(arr)
    return arr


dictionary_file = postings_file = file_of_queries = output_file_of_results = None

try:
    opts, args = getopt.getopt(sys.argv[1:], 'd:p:q:o:')
except getopt.GetoptError:
    usage()
    sys.exit(2)

for o, a in opts:
    if o == '-d':
        dictionary_file  = a
    elif o == '-p':
        postings_file = a
    elif o == '-q':
        file_of_queries = a
    elif o == '-o':
        file_of_output = a
    else:
        assert False, "unhandled option"

if dictionary_file == None or postings_file == None or file_of_queries == None or file_of_output == None :
    usage()
    sys.exit(2)

run_search(dictionary_file, postings_file, file_of_queries, file_of_output)
