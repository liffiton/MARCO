#!/usr/bin/env python3

from src.marco.marco import parse_args, enumerate_with_args


def main():
    args = parse_args()
    for result in enumerate_with_args(args, print_results=True):
        print(result)


if __name__ == '__main__':
    main()
