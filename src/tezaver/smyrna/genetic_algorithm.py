"""
Genetic Algorithm for Feature Selection
========================================
"Evrim ile En İyi DNA Kombinasyonunu Bul"

This algorithm uses evolutionary principles to discover optimal feature
combinations:

1. Population: Random feature subsets
2. Fitness: Cross-validation accuracy
3. Selection: Best-performing subsets survive
4. Crossover: Combine features from two parents
5. Mutation: Random feature changes
6. Evolution: Repeat for N generations

CRITICAL: This explores feature combinations that Backward Elimination 
might miss (synergies between features).
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Set
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


class GeneticAlgorithmMiner:
    """
    Genetic Algorithm for evolving optimal feature subsets.
    """
    
    def __init__(
        self,
        population_size: int = 50,
        generations: int = 20,
        target_feature_count: int = 15,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        elite_size: int = 5,
        cv_folds: int = 3,
        random_state: int = 42
    ):
        """
        Initialize Genetic Algorithm.
        
        Args:
            population_size: Number of individuals (feature subsets)
            generations: Number of evolution cycles
            target_feature_count: Desired number of features
            mutation_rate: Probability of random mutation
            crossover_rate: Probability of crossover
            elite_size: Number of best individuals to keep unchanged
            cv_folds: Cross-validation folds
            random_state: Random seed
        """
        self.population_size = population_size
        self.generations = generations
        self.target_feature_count = target_feature_count
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = elite_size
        self.cv_folds = cv_folds
        self.random_state = random_state
        
        np.random.seed(random_state)
        
        self.evolution_history = []
        self.best_individual = None
        self.best_fitness = 0.0
    
    def initialize_population(
        self,
        all_features: List[str]
    ) -> List[Set[str]]:
        """
        Create initial random population.
        
        Each individual = random subset of features.
        
        Args:
            all_features: All available features
            
        Returns:
            List of feature sets (population)
        """
        population = []
        
        for _ in range(self.population_size):
            # Random subset of target size
            n_features = np.random.randint(
                max(5, self.target_feature_count - 5),
                min(len(all_features), self.target_feature_count + 5)
            )
            individual = set(np.random.choice(
                all_features,
                size=n_features,
                replace=False
            ))
            population.append(individual)
        
        return population
    
    def evaluate_fitness(
        self,
        individual: Set[str],
        X: pd.DataFrame,
        y: pd.Series
    ) -> float:
        """
        Evaluate fitness (CV accuracy) of feature subset.
        
        Args:
            individual: Feature subset
            X: Full feature DataFrame
            y: Labels
            
        Returns:
            Fitness score (accuracy)
        """
        if len(individual) == 0:
            return 0.0
        
        features = list(individual)
        X_subset = X[features]
        
        model = RandomForestClassifier(
            n_estimators=50,  # Reduced for speed
            random_state=self.random_state,
            max_depth=8
        )
        
        try:
            scores = cross_val_score(
                model,
                X_subset,
                y,
                cv=self.cv_folds,
                scoring='accuracy'
            )
            return scores.mean()
        except:
            return 0.0
    
    def selection(
        self,
        population: List[Set[str]],
        fitness_scores: List[float]
    ) -> List[Set[str]]:
        """
        Select best individuals for reproduction.
        
        Uses tournament selection.
        
        Args:
            population: Current population
            fitness_scores: Fitness of each individual
            
        Returns:
            Selected individuals
        """
        # Elite: Keep best individuals unchanged
        sorted_indices = np.argsort(fitness_scores)[::-1]
        elite = [population[i] for i in sorted_indices[:self.elite_size]]
        
        # Tournament selection for rest
        selected = elite.copy()
        
        while len(selected) < self.population_size:
            # Tournament: Pick 3 random, choose best
            tournament_idx = np.random.choice(
                len(population),
                size=3,
                replace=False
            )
            winner_idx = tournament_idx[
                np.argmax([fitness_scores[i] for i in tournament_idx])
            ]
            selected.append(population[winner_idx].copy())
        
        return selected
    
    def crossover(
        self,
        parent1: Set[str],
        parent2: Set[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Crossover: Combine features from two parents.
        
        Args:
            parent1: First parent feature set
            parent2: Second parent feature set
            
        Returns:
            Two children feature sets
        """
        if np.random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()
        
        # Combine all features
        all_features = list(parent1 | parent2)
        
        # Split randomly
        split_point = len(all_features) // 2
        np.random.shuffle(all_features)
        
        child1 = set(all_features[:split_point])
        child2 = set(all_features[split_point:])
        
        return child1, child2
    
    def mutate(
        self,
        individual: Set[str],
        all_features: List[str]
    ) -> Set[str]:
        """
        Mutation: Random feature changes.
        
        Args:
            individual: Feature subset to mutate
            all_features: All available features
            
        Returns:
            Mutated individual
        """
        mutated = individual.copy()
        
        if np.random.random() < self.mutation_rate:
            # Remove random feature
            if len(mutated) > 1:
                mutated.remove(np.random.choice(list(mutated)))
        
        if np.random.random() < self.mutation_rate:
            # Add random feature
            available = set(all_features) - mutated
            if available:
                mutated.add(np.random.choice(list(available)))
        
        return mutated
    
    def mine(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> List[str]:
        """
        Run Genetic Algorithm evolution.
        
        Args:
            X: Feature DataFrame
            y: Labels
            
        Returns:
            Best feature subset found
        """
        logger.info("Starting Genetic Algorithm...")
        logger.info(f"Population: {self.population_size}")
        logger.info(f"Generations: {self.generations}")
        logger.info(f"Target features: {self.target_feature_count}")
        
        all_features = list(X.columns)
        
        # CLEANUP: Remove raw price/volume columns
        blacklist = [
            'open', 'high', 'low', 'close', 'volume', 
            'bb_upper', 'bb_middle', 'bb_lower',
            'ema_9', 'ema_21', 'ema_50', 'ema_200',
            'fib_0.236', 'fib_0.382', 'fib_0.618'
        ]
        
        # Filter features for population initialization
        all_features = [f for f in all_features if f not in blacklist]
        
        # Initialize population
        population = self.initialize_population(all_features)
        
        for generation in range(self.generations):
            logger.info(f"\n--- Generation {generation + 1}/{self.generations} ---")
            
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                fitness = self.evaluate_fitness(individual, X, y)
                fitness_scores.append(fitness)
            
            # Track best
            best_idx = np.argmax(fitness_scores)
            best_fitness = fitness_scores[best_idx]
            best_individual = population[best_idx]
            
            if best_fitness > self.best_fitness:
                self.best_fitness = best_fitness
                self.best_individual = best_individual.copy()
            
            # Log stats
            mean_fitness = np.mean(fitness_scores)
            logger.info(f"Best: {best_fitness:.4f} | Mean: {mean_fitness:.4f} | Features: {len(best_individual)}")
            
            # Record history
            self.evolution_history.append({
                'generation': generation + 1,
                'best_fitness': best_fitness,
                'mean_fitness': mean_fitness,
                'best_feature_count': len(best_individual)
            })
            
            # Selection
            selected = self.selection(population, fitness_scores)
            
            # Crossover & Mutation
            next_generation = []
            
            # Keep elite
            for i in range(self.elite_size):
                next_generation.append(selected[i])
            
            # Generate offspring
            while len(next_generation) < self.population_size:
                # Select two parents
                parent1 = selected[np.random.randint(len(selected))]
                parent2 = selected[np.random.randint(len(selected))]
                
                # Crossover
                child1, child2 = self.crossover(parent1, parent2)
                
                # Mutation
                child1 = self.mutate(child1, all_features)
                child2 = self.mutate(child2, all_features)
                
                next_generation.append(child1)
                if len(next_generation) < self.population_size:
                    next_generation.append(child2)
            
            population = next_generation
        
        # Final evaluation
        logger.info("\n" + "=" * 70)
        logger.info("GENETIC ALGORITHM COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Best fitness: {self.best_fitness:.4f}")
        logger.info(f"Best feature count: {len(self.best_individual)}")
        logger.info(f"\nBest Features:")
        for i, feat in enumerate(sorted(self.best_individual), 1):
            logger.info(f"  {i:2d}. {feat}")
        
        return list(self.best_individual)
    
    def get_evolution_history(self) -> pd.DataFrame:
        """Get evolution history as DataFrame."""
        return pd.DataFrame(self.evolution_history)
