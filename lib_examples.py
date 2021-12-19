#!/usr/bin/env python3
#
# Example invocations demonstrating lib/API interface
#

import sys

from src.marco.marco import parse_args, enumerate_with_args


def example1():
    # Example 1:
    #  Basic usage, specifying arguments and receiving results as printable strings
    print("Example 1")

    args_list = ['tests/test1.cnf', '--threads', '4']
    args_list.extend(sys.argv[1:])
    args = parse_args(args_list)
    for result in enumerate_with_args(args, print_results=True):
        print(result)


def example2():
    # Example 2:
    #  Filter results by type, end early based on a specific condition.
    #  Receive results as tuples.
    print("Example 2")

    results = []
    args_list = ['tests/c10.cnf']
    args_list.extend(sys.argv[1:])
    args = parse_args(args_list)
    # generator can be saved in a variable to call .close() later
    gen = enumerate_with_args(args)
    for result in gen:
        if result[0] == 'U':
            results.append(result)

        if len(results) >= 2:
            # gen.close() will end the enumeration early and clean up
            gen.close()

    print(results)


def main():
    example1()
    example2()


if __name__ == '__main__':
    main()
