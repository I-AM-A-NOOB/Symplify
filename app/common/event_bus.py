# coding: utf-8
"""Event bus for decoupled communication between components.

This module provides a singleton event bus that allows ViewModels and other
components to communicate without direct references, reducing coupling.

Example:
    >>> from app.common.event_bus import event_bus
    >>> 
    >>> # Subscribe to events
    >>> def on_variable_changed(data):
    ...     print(f"Variable {data['name']} changed to {data['value']}")
    >>> 
    >>> event_bus.subscribe("variable_changed", on_variable_changed)
    >>> 
    >>> # Publish events
    >>> event_bus.publish("variable_changed", {"name": "x", "value": 42})
"""
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Singleton event bus for application-wide event communication.
    
    Provides a publish-subscribe pattern for decoupled communication
    between ViewModels and other components.
    
    Attributes:
        _subscribers: Dictionary mapping event names to lists of callbacks.
        
    Example:
        >>> bus = EventBus()
        >>> bus.subscribe("calculation_done", lambda data: print(data))
        >>> bus.publish("calculation_done", {"result": 42})
    """
    
    _instance: Optional["EventBus"] = None
    
    def __new__(cls) -> "EventBus":
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the event bus."""
        if self._initialized:
            return
        super().__init__()
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._initialized = True
    
    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """Subscribe to an event.
        
        Args:
            event_name: The name of the event to subscribe to.
            callback: The function to call when the event is published.
            
        Example:
            >>> bus = EventBus()
            >>> def handler(data):
            ...     print(f"Received: {data}")
            >>> bus.subscribe("my_event", handler)
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
    
    def unsubscribe(self, event_name: str, callback: Callable[[Any], None]) -> bool:
        """Unsubscribe from an event.
        
        Args:
            event_name: The name of the event.
            callback: The callback to remove.
            
        Returns:
            True if the callback was found and removed.
            
        Example:
            >>> bus = EventBus()
            >>> bus.unsubscribe("my_event", handler)
            True
        """
        if event_name in self._subscribers:
            if callback in self._subscribers[event_name]:
                self._subscribers[event_name].remove(callback)
                return True
        return False
    
    def publish(self, event_name: str, data: Any = None) -> None:
        """Publish an event to all subscribers.
        
        Args:
            event_name: The name of the event to publish.
            data: Optional data to pass to subscribers.
            
        Example:
            >>> bus = EventBus()
            >>> bus.publish("variable_changed", {"name": "x", "value": 42})
        """
        if event_name not in self._subscribers:
            return
        
        # Call all subscribers, catching exceptions to prevent one handler
        # from breaking others
        for callback in self._subscribers[event_name].copy():
            try:
                callback(data)
            except Exception:
                # Log error but continue with other subscribers
                import traceback
                traceback.print_exc()
    
    def clear(self, event_name: Optional[str] = None) -> None:
        """Clear all subscribers for an event or all events.
        
        Args:
            event_name: Optional event name to clear. If None, clears all.
            
        Example:
            >>> bus = EventBus()
            >>> bus.clear("variable_changed")  # Clear specific event
            >>> bus.clear()  # Clear all events
        """
        if event_name is None:
            self._subscribers.clear()
        elif event_name in self._subscribers:
            del self._subscribers[event_name]


# Global event bus instance
event_bus = EventBus()


# Predefined event names for type safety
class Events:
    """Predefined event names used throughout the application.
    
    Using these constants instead of string literals helps prevent typos
    and provides IDE autocomplete support.
    
    Example:
        >>> from app.common.event_bus import event_bus, Events
        >>> event_bus.subscribe(Events.VARIABLE_CHANGED, handler)
    """
    
    # Variable events
    VARIABLE_CHANGED = "variable_changed"
    VARIABLE_ADDED = "variable_added"
    VARIABLE_DELETED = "variable_deleted"
    VARIABLE_RENAMED = "variable_renamed"
    VARIABLES_CLEARED = "variables_cleared"
    
    # Calculation events
    CALCULATION_STARTED = "calculation_started"
    CALCULATION_COMPLETED = "calculation_completed"
    CALCULATION_ERROR = "calculation_error"
    
    # History events
    HISTORY_UPDATED = "history_updated"
    HISTORY_CLEARED = "history_cleared"
    
    # Settings events
    SETTINGS_CHANGED = "settings_changed"
    THEME_CHANGED = "theme_changed"
