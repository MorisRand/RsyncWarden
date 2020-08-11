from collections import Counter
from typing import Set

class FailedFiles(Counter): 
    def __init__(self, *args, spurious_treshold=4, **kwargs): 
        self.spurious_files: Set[str] = set() 
        self.integrity_failed_counter: int = 0 
        self.spurious_treshold: int = spurious_treshold 
 
        super().__init__(*args, **kwargs) 
 
    def update(self, *args, **mapping): 
        super().update(*args, **mapping) 
        for key, count in self.items(): 
            if count > self.spurious_treshold: 
                self.spurious_files.add(key) 
