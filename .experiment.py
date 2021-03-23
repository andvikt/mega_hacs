from itertools import permutations

RGB_COMBINATIONS = [''.join(x) for x in permutations('rgb')]

print(RGB_COMBINATIONS)