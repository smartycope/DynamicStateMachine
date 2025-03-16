from src.DynamicStateMachine.DynamicStateMachine import DynamicStateMachine
from src.DynamicStateMachine.States import States

class ExampleStates(States):
    a = 'this is a'
    b = 'this is b'
    pre_c = None
    c = 'this is c'

class ExampleMachine(DynamicStateMachine):
    log = ''

    def do_the_thing(self, decider=True):
        if decider:
            self.log += 'decide: a\n'
            return ExampleStates.a, 'if decider is True'
        else:
            self.log += 'decide: c\n'
            return ExampleStates.pre_c

    def decide_if_done(self, done=False):
        self.log += 'decide if done\n'
        if done:
            self.log += 'done\n'
            return None, 'Im done talking to you now.'
        else:
            self.log += 'not done\n'
            return ExampleStates.a, 'no keep going!'

    def before_a(self):
        self.log += 'before a\n'

    def after_a(self):
        self.log += 'after a\n'

    def before_b(self):
        self.log += 'before b\n'

    def after_b(self):
        self.log += 'after b\n'

    def before_c(self):
        self.log += 'before c\n'

    def after_c(self):
        self.log += 'after c\n'

    def before_pre_c(self):
        self.log += 'before pre_c\n'

    def after_pre_c(self):
        self.log += 'after pre_c\n'

    def on_start(self):
        self.log += 'starting\n'

    def on_end(self):
        self.log += 'finished\n'

    states = ExampleStates
    initial = ExampleStates.a
    transitions = (
        # Can be either simple transitions, like so
        ExampleStates.a >> ExampleStates.b,
        # ...or transition methods that determine the next state
        ExampleStates.b >> do_the_thing,
        ExampleStates.pre_c >> ExampleStates.c,
        # Transition methods can return a state, another transition method, or None
        ExampleStates.c >> decide_if_done,
    )


def test_example_machine():
    # Initial state is a
    m = ExampleMachine()
    # Starting...
    m.next()      # a -> b
    m.next(False) # b -> c
    m.next(False) # c -> a
    next(m)       # a -> b
    m.next(True)  # b -> a
    next(m)       # a -> b
    m.next(False) # b -> c
    m.next(True)  # c -> None
    # Finished!

    # print(m.log)

    assert m.log == """\
starting
before a
after a
before b
decide: c
after b
before pre_c
after pre_c
before c
decide if done
not done
after c
before a
after a
before b
decide: a
after b
before a
after a
before b
decide: c
after b
before pre_c
after pre_c
before c
decide if done
done
finished
""", m.log
