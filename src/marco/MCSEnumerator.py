import array
import os
import queue
import threading

from ..pyminisolvers import minisolvers


class MCSEnumerator(object):
    def __init__(self, csolver, stats, config, pipe=None):
        self.solver = csolver.s
        self.clauses = []
        self.blk_downs = []
        self.blk_ups = []
        self.setup_clauses(csolver.dimacs)
        self.nvars = csolver.nvars
        self.nclauses = csolver.nclauses
        self.n = csolver.n
        self.groups = csolver.groups
        self.instrumented_solver = None
        self.stats = stats
        self.config = config

        # workaround for Python 3.6+ changing defaultdict.iteritems -> defaultdict.items
        if not hasattr(self.groups, 'items'):
            self.groups.items = self.groups.iteritems

        self.pipe = pipe
        # if a pipe is provided, use it to receive results from other enumerators
        if self.pipe:
            self.incoming_queue = queue.Queue()
            self.recv_thread = threading.Thread(target=self.receive_thread)
            self.recv_thread.start()

    def receive_thread(self):
        while self.pipe.poll(None):
            with self.stats.time('receive'):
                res = self.pipe.recv()
                if res == 'terminate':
                    # exit process on terminate message
                    os._exit(0)

                if self.config['comms_ignore']:
                    continue

                self.incoming_queue.put(res)

    def add_received(self, add_to_instrumented=False):
        while not self.incoming_queue.empty():
            rec = self.incoming_queue.get()
            if rec[0] == 'S':
                self.blk_downs.append(rec[1])
                self.block_down(self.solver, rec[1])
                if add_to_instrumented:
                    self.block_down(self.instrumented_solver, rec[1])
            if rec[0] == 'U':
                self.blk_ups.append(rec[1])
                self.block_up(self.solver, rec[1])
                if add_to_instrumented:
                    self.block_up(self.instrumented_solver, rec[1])

    def check_sat(self, solver, assumps=None):
        if self.pipe:
            # Update blocking clauses as close as possible to calling solve()
            self.add_received(add_to_instrumented=(solver == self.instrumented_solver))

        return solver.solve(assumps)

    def setup_clauses(self, dimacs):
        for clause in dimacs:
            self.clauses.append(array.array('i', [int(i) for i in clause.split()[:-1]]))

    def complement(self, aset):
        return set(range(1, self.n+1)).difference(aset)

    def setup_solver(self):
        solver = minisolvers.MinicardSubsetSolver()
        solver.set_varcounts(self.nvars, self.n)

        assert (self.n <= self.nclauses)
        gcnf_in = (self.n != self.nclauses)  # In gcnf, # of groups is less than # of clauses

        # Create new vars
        solver.new_vars(self.nvars + self.n)

        # add clauses ...
        if gcnf_in:
            for groupid, clauses in self.groups.items():
                for j in clauses:
                    if groupid == 0:
                        solver.add_clause(self.clauses[j])
                    else:
                        solver.add_clause_instrumented(self.clauses[j], groupid-1)
        else:
            for i, clause in enumerate(self.clauses):
                solver.add_clause_instrumented(clause, i)
        for clause in self.blk_downs:
            self.block_down(solver, clause)
        for clause in self.blk_ups:
            self.block_up(solver, clause)
        return solver

    def block_down(self, solver, frompoint):
        clause = [i+self.nvars for i in frompoint]
        solver.add_clause(clause)

    def block_up(self, solver, frompoint):
        clause = [-(i+self.nvars) for i in frompoint]
        solver.add_clause(clause)

    def get_MSS(self):
        model = self.instrumented_solver.get_model_trues(offset=1)
        MSS = array.array('i', [x-self.nvars for x in model if x > self.nvars])
        return MSS

    def enumerate(self):
        k = 1  # counting for AtMost constraints
        self.check_sat(self.solver, list(range(self.nvars+1, self.nvars+self.n+1)))
        included = set(self.solver.unsat_core(offset=1))

        while self.check_sat(self.solver):
            self.instrumented_solver = self.setup_solver()
            self.instrumented_solver.add_atmost([-(i+self.nvars) for i in included], k)  # adding a bound for selector variables

            instrumented = [(i+self.nvars) for i in self.complement(included)]
            while self.check_sat(self.instrumented_solver, instrumented):
                MSS = self.get_MSS()
                res = ("S", MSS)
                yield res

                MCS = self.complement(MSS)
                self.blk_downs.append(MCS)  # save for later solvers
                self.block_down(self.solver, MCS)
                self.block_down(self.instrumented_solver, MCS)
            included.update(self.instrumented_solver.unsat_core(offset=1))
            k += 1

        if self.pipe:
            self.pipe.send(('done', self.stats))
            # wait for receive thread to finish processing any incoming data until our "done" is acknowledged by the parent
            self.recv_thread.join()
