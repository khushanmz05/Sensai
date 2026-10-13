"""Unit tests for optimization/optimizer.py."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from optimization.optimizer import PromptOptimizer


class PromptOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.prompts_dir = self.root / 'prompts'
        self.prompts_dir.mkdir()
        (self.prompts_dir / 'rephrase.txt').write_text('Rephrase: {prompt}\n{context}', encoding='utf-8')
        (self.prompts_dir / 'add_constraints.txt').write_text('Constrain: {prompt}\n{context}', encoding='utf-8')
        (self.prompts_dir / 'add_examples.txt').write_text('Example: {prompt}\n{context}', encoding='utf-8')
        self.db_path = self.root / 'history.sqlite3'

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_selects_best_prompt_and_persists_history(self):
        scores = {
            'Initial prompt': 0.50,
            'Initial prompt [rephrase]': 0.55,
            'Initial prompt [add_constraints]': 0.80,
            'Initial prompt [add_examples]': 0.60,
        }

        def variant_generator(prompt, strategy, instruction):
            self.assertIn(prompt, instruction)
            return f'{prompt} [{strategy}]'

        optimizer = PromptOptimizer(
            model='test-model',
            max_iterations=1,
            db_path=self.db_path,
            prompts_dir=self.prompts_dir,
            variant_generator=variant_generator,
        )
        result = optimizer.optimize('Initial prompt',
                                    lambda prompt, _: scores[prompt],
                                    retrieval_context='R1 context')

        self.assertEqual(result.optimized_prompt, 'Initial prompt [add_constraints]')
        self.assertEqual(result.best_score, 0.80)
        self.assertEqual(result.iterations, 1)
        self.assertFalse(result.converged)
        self.assertEqual(result.history[0]['strategy'], 'baseline')
        selected = [row for row in result.history if row['selected']]
        self.assertEqual(len(selected), 2)

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                'SELECT COUNT(*) FROM optimization_history'
            ).fetchone()[0]
            chosen = connection.execute(
                'SELECT strategy FROM optimization_history WHERE iteration = 1 AND selected = 1'
            ).fetchone()[0]
        self.assertEqual(rows, len(result.history))
        self.assertEqual(chosen, 'add_constraints')

    def test_converges_after_three_small_improvements(self):
        calls = {'count': 0}

        def variant_generator(prompt, strategy, instruction):
            del prompt, instruction
            calls['count'] += 1
            iteration = ((calls['count'] - 1) // 3) + 1
            return f'iter{iteration}-{strategy}'

        def ev1(prompt, _):
            if prompt == 'Initial prompt':
                return 100.0
            iteration = int(prompt[4:].split('-')[0])
            return {1: 100.5, 2: 100.8, 3: 101.0, 4: 103.0}[iteration]

        optimizer = PromptOptimizer(
            model='test-model',
            max_iterations=10,
            db_path=self.db_path,
            prompts_dir=self.prompts_dir,
            variant_generator=variant_generator,
        )
        result = optimizer.optimize('Initial prompt', ev1)

        self.assertTrue(result.converged)
        self.assertEqual(result.iterations, 3)
        self.assertEqual(result.best_score, 101.0)

    def test_zero_baseline_score_does_not_force_plateau(self):
        scores = {
            'Initial prompt': 0.0,
            'Initial prompt [rephrase]': 0.1,
            'Initial prompt [add_constraints]': 0.2,
            'Initial prompt [add_examples]': 0.15,
        }

        optimizer = PromptOptimizer(
            model='test-model',
            max_iterations=1,
            db_path=self.db_path,
            prompts_dir=self.prompts_dir,
            variant_generator=lambda prompt, strategy, _: f'{prompt} [{strategy}]',
        )
        result = optimizer.optimize('Initial prompt', lambda prompt, _: scores[prompt])

        self.assertEqual(result.best_score, 0.2)
        self.assertFalse(result.converged)


if __name__ == '__main__':
    unittest.main()
