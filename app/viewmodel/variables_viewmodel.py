# coding: utf-8
"""Variables ViewModel for the Symplify application.

This module provides the ViewModel for the variables interface,
connecting the VariableManager model with the VariablesInterface view.
Uses EventBus for decoupled communication with other ViewModels.

Example:
    >>> from app.model import VariableManager
    >>> from app.viewmodel import VariablesViewModel, LogViewModel
    >>> vm = VariablesViewModel(VariableManager(), LogViewModel())
    >>> vm.add_variable("x", 42)
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QObject, Signal

from ..model.variable import VariableManager, Variable
from ..common.event_bus import event_bus, Events
from .log_viewmodel import LogViewModel


class VariablesViewModel(QObject):
    """ViewModel for the variables interface.
    
    Connects the VariableManager model with the VariablesInterface view.
    Subscribes to EventBus events to stay synchronized with other ViewModels.
    
    Signals:
        variables_updated: Emitted when variables change.
        variable_added: Emitted when a variable is added.
        variable_deleted: Emitted when a variable is deleted.
        variable_renamed: Emitted when a variable is renamed.
        error_occurred: Emitted when an error occurs.
        
    Attributes:
        variable_manager: The VariableManager model instance.
        log_viewmodel: The Log ViewModel for logging.
        
    Example:
        >>> vm = VariablesViewModel(VariableManager(), LogViewModel())
        >>> vm.variables_updated.connect(view.refresh_table)
        >>> vm.add_variable("x", 42)
    """
    
    variables_updated = Signal()
    variable_added = Signal(str, object)  # name, value
    variable_deleted = Signal(str)  # name
    variable_renamed = Signal(str, str)  # old_name, new_name
    error_occurred = Signal(str)
    
    def __init__(
        self,
        variable_manager: VariableManager,
        log_viewmodel: LogViewModel,
        parent: Optional[QObject] = None
    ):
        """Initialize the variables ViewModel.
        
        Args:
            variable_manager: The VariableManager model instance.
            log_viewmodel: The Log ViewModel for logging.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._log_viewmodel = log_viewmodel
        
        # Subscribe to EventBus events from other ViewModels
        self._subscribe_to_events()
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events."""
        event_bus.subscribe(Events.VARIABLE_ADDED, self._on_variable_added_event)
        event_bus.subscribe(Events.VARIABLE_DELETED, self._on_variable_deleted_event)
        event_bus.subscribe(Events.VARIABLE_RENAMED, self._on_variable_renamed_event)
        event_bus.subscribe(Events.VARIABLES_CLEARED, self._on_variables_cleared_event)
    
    def _on_variable_added_event(self, data: Dict[str, Any]) -> None:
        """Handle variable added event from EventBus.
        
        Args:
            data: Event data containing name and value.
        """
        name = data.get("name", "")
        value = data.get("value")
        self.variable_added.emit(name, value)
        self.variables_updated.emit()
    
    def _on_variable_deleted_event(self, data: Dict[str, Any]) -> None:
        """Handle variable deleted event from EventBus.
        
        Args:
            data: Event data containing name.
        """
        name = data.get("name", "")
        self.variable_deleted.emit(name)
        self.variables_updated.emit()
    
    def _on_variable_renamed_event(self, data: Dict[str, Any]) -> None:
        """Handle variable renamed event from EventBus.
        
        Args:
            data: Event data containing old_name and new_name.
        """
        old_name = data.get("old_name", "")
        new_name = data.get("new_name", "")
        self.variable_renamed.emit(old_name, new_name)
        self.variables_updated.emit()
    
    def _on_variables_cleared_event(self, data: Dict[str, Any]) -> None:
        """Handle variables cleared event from EventBus.
        
        Args:
            data: Event data (empty for clear event).
        """
        self.variables_updated.emit()
    
    def add_variable(self, name: str, value: Any) -> bool:
        """Add a new variable.
        
        Args:
            name: The variable name.
            value: The variable value.
            
        Returns:
            True if successful.
            
        Example:
            >>> vm.add_variable("x", 42)
            True
        """
        try:
            self._variable_manager.set(name, value)
            
            # Publish event to notify other ViewModels
            event_bus.publish(Events.VARIABLE_ADDED, {
                "name": name,
                "value": value
            })
            
            # Log the operation
            self._log_viewmodel.add_info(f"Variable added: {name} = {value}", "Variables")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Failed to add variable: {e}", "Variables")
            return False
    
    def delete_variable(self, name: str) -> bool:
        """Delete a variable.
        
        Args:
            name: The variable name to delete.
            
        Returns:
            True if deleted successfully.
            
        Example:
            >>> vm.delete_variable("x")
            True
        """
        try:
            if self._variable_manager.delete(name):
                # Publish event to notify other ViewModels
                event_bus.publish(Events.VARIABLE_DELETED, {
                    "name": name
                })
                
                # Log the operation
                self._log_viewmodel.add_info(f"Variable deleted: {name}", "Variables")
                
                return True
            return False
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Failed to delete variable: {e}", "Variables")
            return False
    
    def rename_variable(self, old_name: str, new_name: str) -> bool:
        """Rename a variable.
        
        Args:
            old_name: The current variable name.
            new_name: The new variable name.
            
        Returns:
            True if renamed successfully.
            
        Example:
            >>> vm.rename_variable("x", "y")
            True
        """
        try:
            if self._variable_manager.rename(old_name, new_name):
                # Publish event to notify other ViewModels
                event_bus.publish(Events.VARIABLE_RENAMED, {
                    "old_name": old_name,
                    "new_name": new_name
                })
                
                # Log the operation
                self._log_viewmodel.add_info(f"Variable renamed: {old_name} -> {new_name}", "Variables")
                
                return True
            return False
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Failed to rename variable: {e}", "Variables")
            return False
    
    def update_variable(self, name: str, value: Any) -> bool:
        """Update a variable's value.
        
        Args:
            name: The variable name.
            value: The new value.
            
        Returns:
            True if updated successfully.
            
        Example:
            >>> vm.update_variable("x", 100)
            True
        """
        try:
            if not self._variable_manager.exists(name):
                self.error_occurred.emit(f"Variable '{name}' does not exist")
                return False
            
            self._variable_manager.set(name, value)
            
            # Publish event to notify other ViewModels
            event_bus.publish(Events.VARIABLE_CHANGED, {
                "name": name,
                "value": value
            })
            
            # Log the operation
            self._log_viewmodel.add_info(f"Variable updated: {name} = {value}", "Variables")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Failed to update variable: {e}", "Variables")
            return False
    
    def get_variables(self) -> Dict[str, Any]:
        """Get all variables.
        
        Returns:
            Dictionary of all variables.
            
        Example:
            >>> vm.get_variables()
            {'x': 42, 'y': 100}
        """
        return self._variable_manager.list_all()
    
    def get_variable_list(self) -> List[Variable]:
        """Get all variables as a list.
        
        Returns:
            List of Variable objects.
            
        Example:
            >>> vm.get_variable_list()
            [Variable(name='x', value=42)]
        """
        return self._variable_manager.list_variables()
    
    def generate_unique_name(self, base: str = "var") -> str:
        """Generate a unique variable name.
        
        Args:
            base: The base name. Defaults to "var".
            
        Returns:
            A unique variable name.
            
        Example:
            >>> vm.generate_unique_name("temp")
            'temp_1'
        """
        return self._variable_manager.generate_unique_name(base)
    
    def validate_name(self, name: str) -> bool:
        """Validate a variable name.
        
        Args:
            name: The name to validate.
            
        Returns:
            True if the name is valid.
            
        Example:
            >>> vm.validate_name("x")
            True
            >>> vm.validate_name("123")
            False
        """
        return self._variable_manager.validate_name(name)
    
    def clear_all(self) -> bool:
        """Clear all variables.
        
        Returns:
            True if cleared successfully.
            
        Example:
            >>> vm.clear_all()
            True
        """
        try:
            self._variable_manager.clear()
            
            # Publish event to notify other ViewModels
            event_bus.publish(Events.VARIABLES_CLEARED, {})
            
            # Log the operation
            self._log_viewmodel.add_info("All variables cleared", "Variables")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Failed to clear variables: {e}", "Variables")
            return False
