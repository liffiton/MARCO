#!/usr/bin/env python3

from src.marco.marco import enumerate_with_args


def main():
    for result in enumerate_with_args(print_results=True):
        print(result)


if __name__ == '__main__':
    main()
