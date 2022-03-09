# Joogle

An indexer and search engine developed for a school assignment. Featuring a simulated SPIMI indexing pattern and a rather limited search engine. Utilizes an untested AND/OR chain optimizer that should theoretically work and other optimization heuristics. The whole thing's kind of a mess but is something I'm quite proud of given the circumstances.

Example query:
bill AND Gates OR NOT (lovEs AND 5G AND NOT oui OR ouii) OR baguette

---

## Indexing

Strips punctuation after tokenization and stemming to remove any stray artifacts. Writes out data to intermediate blocks using json instead of pickle mainly because it was easier to work with. The final output is in binary to benefit search performance.


## Search methodology

Uses the shunting yard algorithm to parse boolean queries. Uses union, intersection and difference to evaluate boolean operators. The processing of NOT terms is delayed until the very end where the NOT operator is only really evaluated if the final result is a NOT term. This significantly reduces the number of expensive operations involving the universal set.

### Simplification rules used

a AND NOT b --> a - b

a OR NOT b --> NOT (b - a)

NOT a AND/OR NOT b --> NOT (a OR/AND b)   - De Morgan's

### Optimization algorithms
Since the shunting yard algorithm groups operators in terms of precendence, in this case OR evaluates after AND, optimizing these chains of operators can be done sequentially and if they reach a certain length threshold. The terms associated with an operator are then reordered based on simplification rules and heuristics to bound the running time. In this section, the size of a term refers to the term's document frequency or the size of its posting list.

#### AND
This optimization isn't really that effective as the nature of the intersection operation coupled with skip pointers already does a pretty decent job in keeping the runtime short. If anything, the number of extra operations in this function would most probably be detrimental for all queries other than extreme edge cases where the largest terms are set to be evaluated first. Thus, the relatively high activation threshold.

NOT operators will be placed on top of the stack in no particular order as they result in a NOT (a + b) term that cannot be optimized. The normal terms will be placed at the bottom with the smallest term at the top to be evaluated first since a AND NOT b will result in a subtraction a - b. This ordering will maximise 'b' while keeping the initial 'a' as small as possible to ensure the smallest possible bound for the subsequent AND operations.

Stack:
BOTTOM | all other normal terms, smallest normal term, NOT, NOT, NOT | TOP

#### OR
This optimization is highly effective, at least theorectically, as again I've never really tested any of this. It is, however, only effective given that there is at least one NOT term present. So this condition, along with the standard query length check, is used to activate the function.

In this operation, all we need to do is to put a NOT term on top of the stack or, in the case of multiple NOT terms, the smallest NOT term (from De Morgan's these become AND operators). Since a OR NOT b === NOT (b - a), a single NOT term is enough cause a cascading effect and transform a series of relatively slow union operations into a series of much more efficient difference operations which also use skip pointers.

Stack:
BOTTOM | literally anything, SMALLEST NOT | TOP



CAUTION: All of this is conjecture and is not based on any maths, theory or real-world testing.
