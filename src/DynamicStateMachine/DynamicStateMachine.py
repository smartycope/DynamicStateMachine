import inspect
from typing import Any, Callable, Iterable, Literal
import dis
import ast
from .State import State
from .States import States

try:
    from graphviz import Digraph
except:
    Diagraph = None


# TODO: allow standalone functions as transition functions (in the works)
# TODO: allow states to be defined in other ways (such as a dict)
# TODO: allow on_ methods, but just have them be identical to the after_ methods. Just cause the naming makes sense
# TODO: add a method that gets run every next call, for side effects -- or maybe not, maybe just override next()? either way, mention in readme
# TODO: mention that anything in the States subclass that starts with an underscore will not be auto-converted
# TODO: instead of a lambda that just returns a state, and a virtual member, instead just allow it to be a State, and the n catch it before we try to call it in next()
# TODO: more tests
# TODO: Convert these todos to github issues
# TODO: implement proper pytest tests
# TODO: run black over everything

TransitionReturn = State | None | tuple[State | None, str]


class DynamicStateMachine:
    """ A state machine that has dynamic transitions between states. It requires an initial state, a
    reference to the States subclass, and a list of transitions. Transitions can be either a simple
    state transition (one state to the next), or a method that will be called to determine the next
    state.

    Methods in this class used as transitions must return one of the following:
        - A member of the States subclass
        - Another transition method of this class that follows the same rules
        - None, to indicate the end of the state machine

    Rules for transitions:
        - Each state should only be on the left hand side (be transitioned from) once (enforced, but not warned)
        - Methods on the right hand side must be methods of this class's subclass, and not standalone functions (this is enforced at the moment)
        - Infinite loops function, and may be intentional, and thus are not checked for
        - Infinite virtual loops (a cycle of all virtual States) will result in a max recursion error. This is not checked for explicitly

    Side effects can be defined using methods named according to the following:
        - before_<step>
        - after_<step>
        - on_<step>
        - on_start
        - on_end2
    """

    states:type[States] = None
    """ The initial state of the state machine """
    initial:State = None
    """ The States subclass that defines the states as class variables """
    transitions:Iterable[tuple[State, Callable[..., TransitionReturn]]] = None
    """ A list of transitions. Each transition is defined by using the >> operator on two states or a
        state and a method. The method must be a method of this class's subclass, and not a standalone
        function.
    """

    def __init__(self, start_immediately=True, trigger_initial_side_effects=True):
        self._trigger_initial_side_effects = trigger_initial_side_effects
        """ If True, then the initial state's before_<state> method will be called on instantiation. """

        self._state = None

        if not (isinstance(self.states, type)): #issubclass(self.states, States)) <- TODO: this should work, NO clue why it doesn't
            raise ValueError(f'states must be a type which is a subclass of States. Got {self.states!r}, which is of type {type(self.states)}')

        if not isinstance(self.initial, State):
            raise ValueError(f'initial must be a State (a member of the states class)')

        if not self.transitions:
            raise ValueError('transitions not specified')

        # Convert the transitions into a dict for faster lookup, ease of internal use, and ensuring uniqueness
        self._transitions:dict[State, Callable] = {s: t for s, t in self.transitions}

        if start_immediately:
            self.start()

    def start(self):
        """ Start the state machine. """
        self.on_start()
        if self._trigger_initial_side_effects:
            self.state = self.initial
        else:
            self._state = self.initial

    def on_start(self):
        """ Called when the state machine is started (when self.start() is called, immediately before the state is set) """

    def on_end(self):
        """ Called when the state machine is ended (immediately after self.state gets set to None) """

    def _call_function_with_correct_params(self, func, *args, **kwargs):
        """ Call a function with the correct parameters. If the function is a method of this class, then
        it will be called with the state machine instance as the first argument. Otherwise, it will be
        called as is. Also, it will only attempt to call the function with the parameters it accepts.
        """
        # TODO: This isn't the best way to detect this
        try:
            if hasattr(self, func.__name__):
                args = (self,) + args
        except:
            raise TypeError('func must be a function')

        # TODO: This maaay fail if positional args are passed in as keyword args. Needs more testing, or better yet,
        # just steal how python-statemachines does it
        sig = inspect.signature(func)
        # Cut args down until it fits the signature
        args = args[:len(sig.parameters)]
        # Remove any kwargs that aren't in the signature
        kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        # bound_args = sig.bind_partial(self, *args, **kwargs)
        # bound_args.apply_defaults()
        return func(*args, **kwargs)

    @property
    def finished(self) -> bool:
        return self._state is None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new:State):
        self.set_state(new)

    def set_state(self, new:State|None|Any|tuple[State|None|Any, str], *args, side_effects=True, **kwargs):
        """ Set the state. This is the setter for self.state, but can also be called directly.
        If side_effects is False, then the before/after methods will not be called.
        Any additional parameters will be passed to both the before/after methods and the transition
        methods.
        This method will run *any* time the state is changed.

        If `new` is a State, it sets it to that state
        If `new` is None, the state gets set to None, self.finished becomes True, and self.on_end() gets called
        If `new` is something else, it tries to find a State in self.states that has the a value as equal to `new`, and
            sets the state equal to that State.
        If `new` is a 2 item tuple of the above, and then a string, in that order, then the state gets applied as above,
            and the string is completely ignored
        """
        old = self._state

        if new is None:
            self._state = None
            self.on_end()
            return

        # type() here is intentional, implicit tuples are going to only ever be just tuples
        # Don't just assume a tuple means what we think it does, since tuples are hashable, they could be used as the
        # values of State's
        if type(new) is tuple and len(new) == 2 and type(new[1]) is str:
            new = new[0]

        if not isinstance(new, State):
            try:
                new = self.states._reverse_states[new]
            except KeyError:
                raise ValueError(f'Invalid state given. Must be a State instance, but got {type(new)}: {new!r}')

        if  new not in self.states._states_list:
            raise ValueError('Invalid state given. self.states be a member of self.states.')

        if side_effects:
            if old is not None:
                if (method := getattr(self, 'after_' + old.name, False)):
                    self._call_function_with_correct_params(method, *args, **kwargs)

            if (method := getattr(self, 'before_' + new.name, False)):
                self._call_function_with_correct_params(method, *args, **kwargs)

            if (method := getattr(self, 'on_' + new.name, False)):
                self._call_function_with_correct_params(method, *args, **kwargs)

        self._state = new

    def next(self, *args, **kwargs):
        """ Transition to the next state. If the next state is a virtual state, then it will
        immediately transition to the state after that.
        Pass along any additional arguments to the transition and side effect methods.
        """
        # Stupid Python not having do-while loops
        do = True
        while not self.finished and (self.state.virtual or do):
            do = False
            # It's can be a method here only breifly, until it returns a state
            # Apparently just adding self like this works
            next_state:State|Callable = self._call_function_with_correct_params(self._transitions[self.state], *args, **kwargs)

            # Keep calling the returned function until it returns a state
            while True:
                try:
                    next_state = self._call_function_with_correct_params(next_state, *args, **kwargs)
                except TypeError:
                    break

            _warning = 'Transition methods must return a transition method, a State, or None'
            # If it returns 2 things, assume the 2nd is a comment for the graphvis graph
            if isinstance(next_state, (list, tuple)):
                assert isinstance(next_state[1], str), _warning
                next_state = next_state[0]

            assert isinstance(next_state, State) or next_state is None, _warning
            # Pass along the args and kwargs, so the before/after methods can use them
            self.set_state(next_state, *args, **kwargs)

    # This would probably be easier and work better if it used ast instead of dis
    @staticmethod
    def get_returns_dis(func):
        # return [instr.argrepr for instr in dis.Bytecode(func) if instr.opname in ("RETURN_CONST", "RETURN_VALUE")]
        rtn = []
        stack = []  # Tracks last loaded values

        for instr in dis.Bytecode(func):
            if instr.opname in {"LOAD_FAST", "LOAD_GLOBAL", "LOAD_DEREF", "LOAD_CONST", 'LOAD_ATTR'}:  # Variable names
                stack.append(instr.argval)
            elif instr.opname == "RETURN_VALUE":
                if stack[-1] is None:
                    stack.pop(-1)
                    continue
                if stack:  # Use last loaded value (var name or literal)
                    rtn.append(stack[-1])
            elif instr.opname == "RETURN_CONST":
                rtn.append(instr.argval)
            elif instr.opname == "BUILD_TUPLE":
                rtn.append((stack.pop(-2), stack.pop(-1)))
                stack.append(None)

        return [((i, '') if type(i) is not tuple else i) for i in rtn]

    # This almost works, but not quite. It wasn't as good of an option as I was hoping
    # Then again, it may work, but what I was testing it with didn't
    @staticmethod
    def get_returns_ast(func):
        class ReturnVisitor(ast.NodeVisitor):
            def __init__(self):
                self.returns = {}

            def visit_FunctionDef(self, node):
                """Handles both function definitions and lambdas."""
                self.generic_visit(node)  # Process child nodes

            def visit_Lambda(self, node):
                """Handles lambda functions."""
                return_value = self.extract_value(node.body)
                self.returns[return_value] = None  # Lambdas don't have doc-like comments after return

            def visit_Return(self, node):
                """Handles return statements and collects potential trailing string literals."""
                return_value = self.extract_value(node.value)
                trailing_string = self.get_trailing_string(node)
                self.returns[return_value] = trailing_string

            def extract_value(self, node):
                """Extracts literals or variable names from AST nodes."""
                if isinstance(node, ast.Constant):  # Literal values (numbers, strings, etc.)
                    return node.value
                elif isinstance(node, ast.Name):  # Variables
                    return node.id
                return "<unknown>"

            def get_trailing_string(self, node):
                """Finds a string literal immediately following a return statement."""
                parent = node.parent
                if parent:
                    body = parent.body
                    try:
                        node_index = body.index(node)
                    except ValueError:
                        body = parent.orelse
                        try:
                            node_index = body.index(node)
                        except ValueError:
                            print('Comment in unhandled place')
                            return
                    if node_index + 1 < len(body):
                        next_node = body[node_index + 1]
                        if isinstance(next_node, ast.Expr) and isinstance(next_node.value, ast.Constant):
                            if isinstance(next_node.value.value, str):  # Must be a string
                                return next_node.value.value
                return None

        source = inspect.getsource(func)
        tree = ast.parse(source)

        # Set parent references for easy access
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

        visitor = ReturnVisitor()
        visitor.visit(tree)
        return visitor.returns

    def construct_graphvis(self,
                           include_start=True,
                           use_names=True,
                           disconnect_virtual=False,
                           split_ends=True,
                           highlighted:State|None=...,
                           graph_attrs={},
                           state_attrs=dict(shape='box', style='rounded'),
                           transition_attrs=dict(shape='oval', style='filled', fillcolor='grey80'),
                           virtual_attrs=dict(shape='box', style='dotted'),
                           start_attrs=dict(shape='box', fillcolor='green', style='filled'),
                           end_attrs=dict(shape='triangle', fillcolor='red', style='filled'),
                           _backend:Literal['dis', 'ast']='dis',
        ) -> Digraph:
        """ Construct a graphviz representation of the current statemachine.
            NOTE: depending on the complexity of the machine, this method may take a while.

            if not include_start, it won't add the "start" entrance node
            if use_names is True, it uses the variable names of the states instead of the values of the states
            if disconnect_virtual is True, it disconnects edges from virtual states and duplicates the nodes at each end
            The state, transition, virtual, start, and end attrs are dicts passed as kwargs to the graphviz.Digraph.node() function when creating the
            corresponding nodes. See https://www.graphviz.org/docs/nodes/ for options
            if split_ends is False, it combines all the "end" nodes into one
            The _backend parameter decides what backend to use to determine the returns of the transition methods. 'dis'
            uses dis.Bytecode to compile the functions, then parse the bytecode for return calls. 'ast' uses the Python
            ast parser to find return statements that way. Currently, only the dis backend is reliable (surprisingly)
            if highlighted is not provided, it will highlight the current step. If it is provided, it will highlight the
            provided step. If it's set to None, no step will be highlighted.
        """
        # Allow the package to be optional
        if not Digraph:
            return

        # optionally be disconnect virtual states
        if 'comment' not in graph_attrs:
            graph_attrs['comment'] = type(self).__name__
        dot = graphviz.Digraph(**graph_attrs)
        handled_transitions = []
        # To ensure all the end nodes have unique names
        # I realized later I could have used monotonic() for this, but it's already implemented this way
        end_counter = 0
        counters = {}
        # Putting this here for efficiency's sake
        state_names = [i.name for i in self.states._states_list]

        def create_destination_state_node(state):
            nonlocal counters
            goto = state.name
            if state.virtual and disconnect_virtual:
                # we need to keep track to ensure uniqueness
                if state.name not in counters:
                    counters[state.name] = 0
                goto = state.name + str(counters[state.name])
                counters[state.name] += 1
                dot.node(goto, state.name, **virtual_attrs)
            return goto

        def add_function_outputs(trans:Callable):
            nonlocal end_counter, handled_transitions

            # For some reason just the reference doesn't work? Unsure why. This works though.
            if trans.__name__ in handled_transitions:
                return
            else:
                handled_transitions.append(trans.__name__)

            if _backend == 'dis':
                items = DynamicStateMachine.get_returns_dis(trans)
            elif _backend == 'ast':
                items = DynamicStateMachine.get_returns_ast(trans).items()
            else:
                raise ValueError(f"_backend value must be either 'dis' or 'ast'. Got {_backend}")

            for ret, comment in items:
                ret: str
                comment: str

                # Goes to the end
                if ret is None:
                    if split_ends or not end_counter:
                        dot.node(f'End{end_counter}', 'End', **end_attrs)
                    dot.edge(trans.__name__, f'End{end_counter}', comment)
                    end_counter += 1

                # Goes to another state
                elif ret in state_names:
                    state = self.states._states[ret]
                    goto = create_destination_state_node(state)
                    dot.edge(trans.__name__, goto, comment)

                # Goes to another transition function to decide where to go next
                # TODO: in order to support standalone functions, this if statement will have to be changed
                elif hasattr(self, ret):
                    lbl = ret
                    if not use_names:
                        lbl = lbl.replace('_', ' ')
                    dot.node(ret, lbl, **transition_attrs)
                    dot.edge(trans.__name__, ret, comment)
                    add_function_outputs(getattr(self, ret))

                else:
                    raise ValueError(f'return value is not a state, None, nor a transition function. Got {ret!r}')

        if include_start:
            dot.node('Start', 'Start', **start_attrs)
            dot.edge('Start', self.initial.name)

        # Add states as nodes
        for state, transition in self._transitions.items():
            state: State
            transition: Callable

            # No idea why it's state.value.value here, instead of state.value
            label = state.name if use_names else state.value

            dot.node(state.name, label, **(virtual_attrs if state.virtual else state_attrs))
            if state._simple:
                goto = create_destination_state_node(state._simple)
                dot.edge(state.name, goto)

            # If it's not simple, then it's a function
            else:
                lbl = transition.__name__
                if not use_names:
                    lbl = lbl.replace('_', ' ')
                dot.node(transition.__name__, lbl, **transition_attrs)
                dot.edge(state.name, transition.__name__)

                add_function_outputs(transition)

        if highlighted is Ellipsis:
            dot = DynamicStateMachine.highlight_node(dot, self.state.name)
        elif highlighted:
            assert isinstance(highlighted, State), 'highlighted must be a State'
            dot = DynamicStateMachine.highlight_node(dot, highlighted.name)

        return dot

    def __next__(self):
        self.next()

    @staticmethod
    def highlight_node(graph:Digraph, id:str, color='blue', style='bold', **attrs):
        if Digraph:
            graph.node(id, color=color, style=style, **attrs)
            return graph
