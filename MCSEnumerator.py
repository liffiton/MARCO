from pyminisolvers import minisolvers
import threading
try:
    import queue
except ImportError:
    import Queue as queue


class MCSEnumerator(object):
    def __init__(self, csolver, stats, pipe):
        self.solver = csolver.s
        self.clauses = []
        self.blk_down = []
        self.blk_up = []
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
                if res == "okay":
                    # received after sending "done" and parent okays this child to close
                    return  # triggers join() in enumerate()
                self.incoming_queue.put(res)

    def add_received(self, add_to_instrumented=False):
        while not self.incoming_queue.empty():
            rec = self.incoming_queue.get()
            if rec[0] == 'S':
                self.blk_down.append(rec[1])
                self.block_down(self.solver, rec[1])
                if add_to_instrumented:
                    self.block_down(self.instrumented_solver, rec[1])
            if rec[0] == 'U':
                self.blk_up.append(rec[1])
                self.block_up(self.solver, rec[1])
                if add_to_instrumented:
                    self.block_up(self.instrumented_solver, rec[1])

    def check_sat(self, solver):
        # Update blocking clauses as close as possible to calling solve()
        self.add_received(add_to_instrumented=(solver == self.instrumented_solver))

        return solver.solve()

    def setup_clauses(self, dimacs):
        for clause in dimacs:
            self.clauses.append([int(i) for i in clause.split()[:-1]])

    def complement(self, aset):
        return set(range(1, self.nclauses+1)).difference(aset)

    def setup_solver(self):
        solver = minisolvers.MinicardSubsetSolver()
        while solver.nvars() < self.nvars:
            solver.new_var()
        for clause in self.clauses:
            sel_var = solver.new_var() + 1
            solver.add_clause([-sel_var]+clause)
        for clause in self.blk_down:
            self.block_down(solver, clause)
        for clause in self.blk_up:
            self.block_up(solver, clause)
        return solver

    def block_down(self, solver, frompoint):
        clause = [i+self.nvars for i in self.complement(frompoint)]
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

        while self.check_sat(self.solver):
            self.instrumented_solver = self.setup_solver()
            sel_vars = list(range(-(self.nvars+1), -(self.nvars+self.nclauses+1), -1))  # generate a list of clause selector vars
            self.instrumented_solver.add_atmost(sel_vars, k)  # adding a bound for selector variables

            while self.check_sat(self.instrumented_solver):
                MSS = self.get_MSS()
                res = ("S", MSS)
                self.pipe.send(res)
                self.blk_down.append(MSS)  # save for later solvers
                self.block_down(self.solver, MSS)
                self.block_down(self.instrumented_solver, MSS)
            k += 1
        self.pipe.send(('done', self.stats))

        # wait for receive thread to finish processing any incoming data until our "done" is acknowledged by the parent
        self.receive_thread.join()
