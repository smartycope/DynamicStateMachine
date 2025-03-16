
from typing import Any, Callable


class State:
    """ A state in our state machine. It holds a name, a value, and a transition, and can be connected
    to other states via the `>>` operator.
    """

    def __init__(self, name:str, value:Any, virtual=False):
        self.name = name
        """ The variable name of the state when it was defined """
        self.value = value
        """ The value of the state when it was defined. Intentionally untyped. """
        self.transition:Callable = None
        """ The transition function to the next state. Gets called to determine the state after this one. """
        self.virtual = virtual
        """ A virtual state is one that immediately transitions to the next state without requiring a call to `next()`. """
        self._simple = None
        """ A state is simple if it only transitions to a single state. """

    def __rshift__(self, other):
        """ If the right hand side is a State, then it's a simple transition, and self.transition
        gets set to a lambda that returns the given state.
        If it's a method then it will be called to determine the next state.
        NOTE: `other` must be a method of the DynamicStateMachine subclass! It cannot be a standalone function.
        (at least for now)
        """
        if isinstance(other, State):
            self._simple = other
            self.transition = lambda *args, **kwargs: other
        elif callable(other):
            self._simple = False
            self.transition = other
        else:
            raise ValueError('Invalid transition')

        return self, self.transition

    def __eq__(self, other):
        if isinstance(other, State):
            return self.value == other.value and self.name == other.name
        elif isinstance(other, str):
            return self.value == other
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f'<State {self.name}>'
