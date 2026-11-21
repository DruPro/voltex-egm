# Design: tree-shaped rules (the route to circuits)

Status: design only. Nothing is implemented, and these hypotheses are not yet pre-registered;
they will be fixed, hashed and timestamped in PREREGISTRATION.md before any code runs. When
built, the feature is an experimental setting, off by default, gated byte-identical to the
current engine when off.

## Why

The multi-premise study's XOR test (`studies/multipremise/tools/x1_xor_circuit.py`): 300 gates,
outputs taught for 200. No configuration learned anything (0 right, 0 wrong). A gate's output
depends on two inputs at once, and every shape the engine can learn is a single path: a
chain follows one branch only. Conditions only constrain the rule's head subject.

## The shape

A tree-shaped rule joins several paths that start from the same entity, with constants
allowed at the leaves:

```
g has output w  &  g has kind xor
                &  g has first input  x  &  x has value one
                &  g has second input y  &  y has value zero
  =>  w has value one
```

Read as a tree rooted at the gate `g`: branches to its kind, to each input's value, and to the
output wire the conclusion is about. Two-premise rules and paths are the special case with
one branch, so the new family contains the old one.

## Search, guided by evidence as before

1. **Anchor.** For each target relation T(w, v), find the entities linked to w by one step
   (for example, the gate whose output w is).
2. **Branches.** From each anchor, collect short paths (1–2 steps) that end at a constant
   (a value word such as `one`, `xor`) or at another variable, counting how often each
   branch occurs among T's stated facts.
3. **Combine.** Build candidate trees from 2–4 frequent branches, keeping only combinations
   seen with at least `SUPPORT` stated conclusions. This mirrors how path rules were
   proposed from paths that connect stated pairs, so the search never enumerates every
   combination.
4. **Score** with the shipped statistics: chains (now tree matches) seen, conclusions stated,
   rate, base rate, lift, known-answer agreement and a z-test.

## Lessons carried over from the multi-premise study

- **No coverage correction** for the new shape until it has been validated on it (round 1's
  collapse came from that correction applied to unvalidated shapes).
- **A cost per branch and per constant**, so a shorter explanation wins unless a larger tree
  adds real predictive value (the redundancy and coincidence problems of long chains).
- **Multiple-comparison control:** the number of candidate trees grows quickly, so the
  acceptance z-threshold should account for how many were tested.
- **Missing is not false:** an entity whose branch value is unobserved neither supports nor
  contradicts a tree.
- **Simple structures only:** no entity may appear twice in one tree match (the tautology
  problem from round 1, generalized).

## Worlds and hypotheses to pre-register

- **Single gates.** XOR, AND, OR, NAND tables over 300 gates, two-thirds taught. Expected: each
  gate type learned as up to four tree rules (one per input pattern), unseen outputs correct.
- **Circuits.** A 4-bit ripple-carry adder described as gate and wire facts; gate behaviors
  taught on separate example gates; inputs given, outputs hidden. Expected: with `DEPTH 0`,
  inference evaluates the circuit and computes the sum for every input pair. This is the
  "calculator learned from examples" demonstration.
- **No harm:** the hidden world, the company world and the four unchanged worlds, as in the
  multi-premise study, with the new setting on.
- **Decoys:** gates whose outputs are random. Expected: no tree accepted.
- **Cost:** rule mining time against the size of the branch vocabulary.

## Open questions

- How many leaf constants a tree may carry before it becomes a memorized lookup table.
- Whether trees should be allowed to refine path rules, or kept a separate family.
- How to show a tree rule's proof readably: it has several premise branches, not one chain.
