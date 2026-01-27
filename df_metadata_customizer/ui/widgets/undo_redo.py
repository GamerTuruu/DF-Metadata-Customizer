"""Undo/Redo system for metadata changes."""

from typing import Callable, Any
from dataclasses import dataclass


@dataclass
class UndoRedoAction:
    """Represents an undo/redo action."""

    name: str
    undo_fn: Callable[[], None]
    redo_fn: Callable[[], None]


class UndoRedoManager:
    """Manager for undo/redo operations."""

    def __init__(self, max_history: int = 100) -> None:
        """Initialize undo/redo manager."""
        self.max_history = max_history
        self.undo_stack: list[UndoRedoAction] = []
        self.redo_stack: list[UndoRedoAction] = []

    def add_action(self, name: str, undo_fn: Callable[[], None], redo_fn: Callable[[], None]) -> None:
        """Add an action to the undo stack."""
        action = UndoRedoAction(name=name, undo_fn=undo_fn, redo_fn=redo_fn)
        self.undo_stack.append(action)
        
        # Clear redo stack when new action is added
        self.redo_stack.clear()
        
        # Limit history size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    def undo(self) -> bool:
        """Undo last action."""
        if not self.undo_stack:
            return False
        
        action = self.undo_stack.pop()
        action.undo_fn()
        self.redo_stack.append(action)
        
        return True

    def redo(self) -> bool:
        """Redo last undone action."""
        if not self.redo_stack:
            return False
        
        action = self.redo_stack.pop()
        action.redo_fn()
        self.undo_stack.append(action)
        
        return True

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        """Clear all history."""
        self.undo_stack.clear()
        self.redo_stack.clear()

    def get_undo_name(self) -> str | None:
        """Get name of next undo action."""
        if self.undo_stack:
            return self.undo_stack[-1].name
        return None

    def get_redo_name(self) -> str | None:
        """Get name of next redo action."""
        if self.redo_stack:
            return self.redo_stack[-1].name
        return None
