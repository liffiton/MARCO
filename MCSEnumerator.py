from pyminisolvers import minisolvers
import sys
import threading
try:
    import queue
except ImportError:
    import Queue as queue


class MCSEnumerator(object):
    def __init__(self, csolver, stats, pipe):
        self.solver = csolver.s
        self.clauses = []
        self.blk_downs = []
        self.blk_ups = []
        self.setup_clauses(csolver.dimacs)
        self.nvars = csolver.nvars
        self.nclauses = csolver.nclauses
        self.instrumented_solver = None
        self.stats = stats
        self.pipe = pipe
        self.incoming_queue = queue.Queue()

        self.receive_thread = threading.Thread(target=self.receive_thread)
        self.receive_thread.daemon = True
        self.receive_thread.start()

    def receive_thread(self):
        while self.pipe.poll(None):
            with self.stats.time('receive'):
                res = self.pipe.recv()
                if res == 'terminate':
                    # exit process on terminate message
                    sys.exit(0)
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
        # Update blocking clauses as close as possible to calling solve()
        self.add_received(add_to_instrumented=(solver == self.instrumented_solver))

        return solver.solve(assumps)

    def setup_clauses(self, dimacs):
        for clause in dimacs:
            self.clauses.append([int(i) for i in clause.split()[:-1]])

    def complement(self, aset):
        return set(range(1, self.nclauses+1)).difference(aset)

    def setup_solver(self):
        solver = minisolvers.MinicardSubsetSolver()
        solver.set_varcounts(self.nvars, self.nclauses)  # fix the TypeError bug in pyminisolver
        while solver.nvars() < self.nvars + self.nclauses:
            solver.new_var()
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
        model = set(self.instrumented_solver.get_model_trues(offset=1))
        MSS = [x-self.nvars for x in model if x > self.nvars]
        return MSS  # return a list of clause selector vars, not the actual clause indices

    def enumerate(self):
        k = 1  # counting for AtMost constraints
        self.check_sat(self.solver, list(range(self.nvars+1, self.nvars+self.nclauses+1)))
        included = set(self.solver.unsat_core(offset=1))

        while self.check_sat(self.solver):
            self.instrumented_solver = self.setup_solver()
            self.instrumented_solver.add_atmost([-(i+self.nvars) for i in included], k)  # adding a bound for selector variables

            instrumented = [(i+self.nvars) for i in self.complement(included)]
            while self.check_sat(self.instrumented_solver, instrumented):
                MSS = self.get_MSS()
                res = ("S", MSS)
                self.pipe.send(res)
                MCS = self.complement(MSS)
                self.blk_downs.append(MCS)  # save for later solvers
                self.block_down(self.solver, MCS)
                self.block_down(self.instrumented_solver, MCS)
            included.update(self.instrumented_solver.unsat_core(offset=1))
            k += 1
        self.pipe.send(('done', self.stats))

        # wait for receive thread to finish processing any incoming data until our "done" is acknowledged by the parent
        self.receive_thread.join()
