from .State import State
from typing import Any

class States:
    """ An abstract class that must be subclassed to define states. It will automatically create State instances
    for each class variable defined in the subclass. If a variable is set to None, then it will be considered a
    "virtual state", and will immediately transition to the next state without requiring a call to `next()`.
    In the future, instancing States directly will be supported, but it's not yet.
    """

    def __init_subclass__(cls, /, virtual_value=None):
        cls._states: dict[str: State] = {}
        """ A dict of all states, with the name as the key and the State instance as the value """
        cls._reverse_states:dict[Any, State] = {}
        """ A dict of all states, with the value as the key and the State instance as the value """
        cls._states_list = []
        """ A list of all states, in the order they were defined """
        cls._virtual_value = virtual_value
        """ The value which you set a state to in order to mark it as a virtual state """

        for name, value in cls.__dict__.items():
            if not name.startswith('_'):
                state = State(name, value, virtual=value is virtual_value)
                cls._states[name] = state
                cls._reverse_states[value] = state
                cls._states_list.append(state)
                setattr(cls, name, state)
