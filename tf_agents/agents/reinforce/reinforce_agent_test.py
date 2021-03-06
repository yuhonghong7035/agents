# coding=utf-8
# Copyright 2018 The TF-Agents Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for TF Agents reinforce_agent."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import tensorflow_probability as tfp

from tf_agents.agents.reinforce import reinforce_agent
from tf_agents.environments import time_step as ts
from tf_agents.networks import network
from tf_agents.specs import tensor_spec

nest = tf.contrib.framework.nest


class DummyActorNet(network.Network):

  def __init__(self, observation_spec, action_spec, unbounded_actions=False):
    # When unbounded_actions=True, we skip the final tanh activation and the
    # action shift and scale. This allows us to compute the actor and critic
    # losses by hand more easily.
    super(DummyActorNet, self).__init__(
        observation_spec=observation_spec,
        action_spec=action_spec,
        state_spec=(),
        name='DummyActorNet')
    single_action_spec = nest.flatten(action_spec)[0]
    activation_fn = None if unbounded_actions else tf.nn.tanh
    self._layers = [
        tf.keras.layers.Dense(
            single_action_spec.shape.num_elements() * 2,
            activation=activation_fn,
            kernel_initializer=tf.constant_initializer([2, 1]),
            bias_initializer=tf.constant_initializer([5]),
        ),
    ]

  def call(self, observations, step_type, network_state):
    del step_type

    states = tf.cast(nest.flatten(observations)[0], tf.float32)
    for layer in self.layers:
      states = layer(states)

    single_action_spec = nest.flatten(self._action_spec)[0]
    actions, stdevs = tf.split(states, 2, axis=1)
    actions = tf.reshape(actions, [-1] + single_action_spec.shape.as_list())
    stdevs = tf.reshape(stdevs, [-1] + single_action_spec.shape.as_list())
    actions = nest.pack_sequence_as(self._action_spec, [actions])
    stdevs = nest.pack_sequence_as(self._action_spec, [stdevs])

    distribution = nest.map_structure_up_to(
        self._action_spec, tfp.distributions.Normal, actions, stdevs)
    return distribution, network_state


class ReinforceAgentTest(tf.test.TestCase):

  def setUp(self):
    super(ReinforceAgentTest, self).setUp()
    self._obs_spec = tensor_spec.TensorSpec([2], tf.float32)
    self._time_step_spec = ts.time_step_spec(self._obs_spec)
    self._action_spec = tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1)

  def testCreateAgent(self):
    reinforce_agent.ReinforceAgent(
        self._time_step_spec,
        self._action_spec,
        actor_network=DummyActorNet(
            self._obs_spec, self._action_spec, unbounded_actions=False),
        optimizer=None,
    )

  def testPolicyGradientLoss(self):
    agent = reinforce_agent.ReinforceAgent(
        self._time_step_spec,
        self._action_spec,
        actor_network=DummyActorNet(
            self._obs_spec, self._action_spec, unbounded_actions=True),
        optimizer=None,
    )

    observations = tf.constant([[1, 2], [3, 4]], dtype=tf.float32)
    time_steps = ts.restart(observations, batch_size=2)
    actions = tf.constant([[0], [1]], dtype=tf.float32)
    returns = tf.constant([1.9, 1.0], dtype=tf.float32)

    expected_loss = 10.983667373657227
    loss = agent.policy_gradient_loss(time_steps, actions, returns)

    self.evaluate(tf.global_variables_initializer())
    loss_ = self.evaluate(loss)
    self.assertAllClose(loss_.loss, expected_loss)

  def testPolicy(self):
    agent = reinforce_agent.ReinforceAgent(
        self._time_step_spec,
        self._action_spec,
        actor_network=DummyActorNet(
            self._obs_spec, self._action_spec, unbounded_actions=False),
        optimizer=None,
    )
    observations = tf.constant([[1, 2]], dtype=tf.float32)
    time_steps = ts.restart(observations, batch_size=2)
    actions = agent.policy().action(time_steps).action
    self.assertEqual(actions.shape.as_list(), [1, 1])

    self.evaluate(tf.global_variables_initializer())
    _ = self.evaluate(actions)


if __name__ == '__main__':
  tf.test.main()
