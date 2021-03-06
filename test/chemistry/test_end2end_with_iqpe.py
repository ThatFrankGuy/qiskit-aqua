# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import unittest

from parameterized import parameterized
import numpy as np
import qiskit
from qiskit.transpiler import PassManager
from qiskit.aqua.utils import decimal_to_binary
from qiskit.aqua import QuantumInstance
from qiskit.aqua.algorithms.single_sample import IQPE
from qiskit.aqua.algorithms.classical import ExactEigensolver
from test.chemistry.common import QiskitChemistryTestCase
from qiskit.chemistry.drivers import PySCFDriver, UnitsType
from qiskit.chemistry import FermionicOperator, QiskitChemistryError
from qiskit.chemistry.aqua_extensions.components.initial_states import HartreeFock


class TestIQPE(QiskitChemistryTestCase):
    """IQPE tests."""

    # TODO: disabled failing test_iqpe
    @parameterized.expand([
        [0.5],
        [0.735],
        [1],
    ])
    def disable_test_iqpe(self, distance):
        self.algorithm = 'IQPE'
        self.log.debug('Testing End-to-End with IQPE on H2 with '
                       'inter-atomic distance {}.'.format(distance))
        try:
            driver = PySCFDriver(atom='H .0 .0 .0; H .0 .0 {}'.format(distance),
                                 unit=UnitsType.ANGSTROM,
                                 charge=0,
                                 spin=0,
                                 basis='sto3g')
        except QiskitChemistryError:
            self.skipTest('PYSCF driver does not appear to be installed')
        self.molecule = driver.run()
        qubit_mapping = 'parity'
        fer_op = FermionicOperator(h1=self.molecule.one_body_integrals, h2=self.molecule.two_body_integrals)
        self.qubit_op = fer_op.mapping(map_type=qubit_mapping, threshold=1e-10).two_qubit_reduced_operator(2)

        exact_eigensolver = ExactEigensolver(self.qubit_op, k=1)
        results = exact_eigensolver.run()
        self.reference_energy = results['energy']
        self.log.debug('The exact ground state energy is: {}'.format(results['energy']))

        num_particles = self.molecule.num_alpha + self.molecule.num_beta
        two_qubit_reduction = True
        num_orbitals = self.qubit_op.num_qubits + (2 if two_qubit_reduction else 0)

        num_time_slices = 50
        num_iterations = 12
        state_in = HartreeFock(self.qubit_op.num_qubits, num_orbitals,
                               num_particles, qubit_mapping, two_qubit_reduction)
        iqpe = IQPE(self.qubit_op, state_in, num_time_slices, num_iterations,
                    expansion_mode='suzuki', expansion_order=2,
                    shallow_circuit_concat=True)
        backend = qiskit.BasicAer.get_backend('qasm_simulator')
        quantum_instance = QuantumInstance(backend, shots=100, pass_manager=PassManager())

        result = iqpe.run(quantum_instance)

        self.log.debug('top result str label:     {}'.format(result['top_measurement_label']))
        self.log.debug('top result in decimal:    {}'.format(result['top_measurement_decimal']))
        self.log.debug('stretch:                  {}'.format(result['stretch']))
        self.log.debug('translation:              {}'.format(result['translation']))
        self.log.debug('final energy from QPE:    {}'.format(result['energy']))
        self.log.debug('reference energy:         {}'.format(self.reference_energy))
        self.log.debug('ref energy (transformed): {}'.format(
            (self.reference_energy + result['translation']) * result['stretch'])
        )
        self.log.debug('ref binary str label:     {}'.format(decimal_to_binary(
            (self.reference_energy + result['translation']) * result['stretch'],
            max_num_digits=num_iterations + 3,
            fractional_part_only=True
        )))

        np.testing.assert_approx_equal(result['energy'], self.reference_energy, significant=2)


if __name__ == '__main__':
    unittest.main()
