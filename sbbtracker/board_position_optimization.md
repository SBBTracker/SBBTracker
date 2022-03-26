# Board Position optimization notes

## Assumptions and biases of approaches

All approaches will be biased toward the board that you are facing.
All results must be considered with this in mind.
An example was playing in the finals as evils vs slay:
to give myself a better chance of winning I needed to move my pumpkin king from slot 7 to slot 4.
This result makes sense, but is not generally applicable, it was only applicable to that matchup

No solution will be perfect. With all approaches there is no garuntee of a global optimum, however;

## Constraints

- There are 7! = 5040 arrangements of a full borad. We can not simulate them all and we cannot


## History of approach

I started with creating a feature for allowing users to select a number of characters to permute
(in practive up to 3 characters) run a simulation for each permutation

This was very useful for learning but was difficult for finding truely optimized board arrangements

It was suggested to look into the Multi-Armed Bandit Problem, this yeilded reasonable results but was slow for 4 characters and still would be intractable for finding the optimal board state.
The issue with the approaches is that they mostly optimize for the number of "pulls" i.e. the total number of simulations run. So the basic approach I implemented first simulated all permutations ~60 times each, eliminated half of the permutations, then simulated each permutation ~120 times; however, this doesn't optimize for the fact that running the simulation 100 times twice is much more expensive than just running the simulation 200 times.

This leads to searching algoithms. The next step is to implement a simple gradient descent with random restarts method. The difficult thing here will be modeling the distance between two board configurations.
The goal is to implement a method that relies on:
 - obtaining the win % for a state
 - running the least number of states before finding a minima
This should be doable - time to try

## Gradient Descent
Gradient descent approach:
 - choose random permutation, choose n "closest" states
    - maybe should seed with player's board first
 - run simulation for the neighbors
 - choose best
 - repeat until local minima
 - record result
 - repeat all of above


### Gradient descent

for a piece there are 2-4 nearest moves
for a given board state there are 9 nearest moves by the "simple distance method"
there are 24 one-swap neighbors

for first attempt, will try 9 nearest positions
find best, make swap, then look at 8 remaining nearest neighbors, etc
can you hash a hash map?

once at best, randomize board?

```
# search for one local maxima
last_res = None
current_board = None
simulated_boards = []
for _ in range(10):
    if current_board is None:
        current_board = board
    else:
        current_board = randomize(board, simulated_boards)

    while True:
        step_results = {}
        for move in moves:
            new_board = move(current_board)
            if hash(new_board) in simulated_boards:
                continute
            step_results[hash(new_board)] = simulate(new_board)
            simulated_boards.append(hash(new_board))

        if not step_results:
            print("all neighbors previously simulated")
            break

        max_res = max(step_results.values())
        current_board = next(
            brd
            for brd, res in step_results.items()
            if res == max_res
        )
        # if all options get worse, break
        if max_res < last_res:
            break
        last_res = max_res

```



### Distance in board states

#### Simplest:
 - 1 <-> 2 = 1
 - 1 <-> 5 = 1
 - 2 <-> 3 = 1
 - 2 <-> 5 = 1
 - 2 <-> 6 = 1
 - 3 <-> 4 = 1
 - 4 <-> 7 = 1
 - 5 <-> 6 = 1
 - 6 <-> 7 = 1

put another way a map from slot to distance-one moves is:
{
    1: (2, 5),
    2: (1, 3, 5, 6),
    3: (2, 4, 6, 7),
    4: (3, 7),
    5: (1, 2, 6),
    6: (2, 3, 5, 7),
    7: (3, 4, 6),
}

#### moving from front to back is half point

 - 1 <-> 2 = 1
 - 1 <-> 5 = 1.5
 - 2 <-> 3 = 1
 - 2 <-> 5 = 1.5
 - 2 <-> 6 = 1.5
 - 3 <-> 4 = 1
 - 4 <-> 7 = 1.5
 - 5 <-> 6 = 1
 - 6 <-> 7 = 1.5




