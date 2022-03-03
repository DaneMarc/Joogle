# Joogle

A SPIMI indexer and search engine that uses boolean retrieval. Utilizes an untested AND/OR chain optimizer that should theoretically work and other optimization heuristics. The whole thing's kind of a mess but is something I'm quite proud of.

---

## Indexing

Strips punctuation after tokenization and stemming to remove any stray artifects. Writes out data to intermediate blocks using json instead of pickle mainly because it was easier to work with. The final output is in binary to benefit search performance.


## Search methodology

Uses the shunting yard algorithm to parse boolean queries. Uses union, intersection and difference to evaluate boolean operators. The processing of NOT terms is delayed until the very end where the NOT operator is only really evaluated if the final result is a NOT term. This significantly reduces the number of expensive operations involving the universal set.

### Simplification rules used

a AND NOT b --> a - b

a OR NOT b --> NOT (b - a)

NOT a AND/OR NOT b --> NOT (a OR/AND b)   -De Morgan's

### Optimization algorithms
Since the shunting yard algorithm groups operators in terms of precendence, in this case AND after OR so that it can be evaluated first from the stack, optimizing these chains of operators can be done sequentially and if they reach a certain length threshold. The terms associated with each operator are then collected and grouped with normal and NOT terms. The terms are subsequently sorted based on the above simplification rules and heuristics to bound the running time.

#### AND
NOT operators will be placed on top of the stack in no particular order as they result in a NOT (a + b) term that cannot be optimized. The normal terms will be placed at the bottom in ascending order (smallest to be evaluated first) since a AND NOT b will result in a subtraction a - b. Thus, this will maximise b while keeping the initial a as small as possible to ensure the smallest possible bound for the subsequent AND operations.

Stack:
BOTTOM | big, med, small, NOT, NOT, NOT | TOP

#### OR
NOT operators will be placed on top of the stack in descending order as they result in a NOT (a . b) term. Essentially, we're trying to optimize the AND operations that result from the double NOT OR terms. The normal terms will be placed at the bottom in no particular order since they are OR operations that cannot be optimized. However, unlike the AND operator, a single NOT term is enough to cause a chain reaction of difference evaluations instead of join evaluations somewhat cannibalizing the normal terms so to speak. Thus, the threshold for the OR optimization is lower as we only need 1 NOT term to be evaluated at the front to start the cascade and avoid join evals.

Stack:
BOTTOM | med, big, small, BIG_NOT, MED_NOT, SMALL_NOT | TOP



CAUTION: All of this is conjecture and is not based on any maths, theory or real-world testing.
