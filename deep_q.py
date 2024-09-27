# Adapted from https://github.com/mswang12/minDQN

# MIT License

# Copyright (c) 2020 Mike

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import random
from collections import deque

import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from gymnasium.envs.registration import register
from tensorflow import keras

from game_data.skill_cards import SkillCards


register(
    id="Gakumas-v0",
    entry_point="gakumas_env:GakumasEnv",
    max_episode_steps=300,
)

env = gym.make("Gakumas-v0")

RANDOM_SEED = 69
random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

print("Action Space: {}".format(env.action_space))
print("State space: {}".format(env.observation_space))

train_episodes = 1200
test_episodes = 100


def agent(state_shape, action_shape):
    learning_rate = 3e-4
    init = tf.keras.initializers.HeUniform()
    model = keras.Sequential()
    model.add(
        keras.layers.Dense(
            64, input_shape=state_shape, activation="relu", kernel_initializer=init
        )
    )
    model.add(keras.layers.Dense(64, activation="relu", kernel_initializer=init))
    model.add(
        keras.layers.Dense(action_shape, activation="linear", kernel_initializer=init)
    )
    model.compile(
        loss=tf.keras.losses.Huber(),
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        metrics=["accuracy"],
    )
    return model


def get_qs(model, state, step):
    return model.predict(state.reshape([1, state.shape[0]]))[0]


def train(env, replay_memory, model, target_model, done):
    learning_rate = 0.7
    discount_factor = 0.618

    MIN_REPLAY_SIZE = 1000
    if len(replay_memory) < MIN_REPLAY_SIZE:
        return

    batch_size = 64 * 2
    mini_batch = random.sample(replay_memory, batch_size)
    current_states = np.array([transition[0] for transition in mini_batch])
    current_qs_list = model.predict(current_states)
    new_current_states = np.array([transition[3] for transition in mini_batch])
    future_qs_list = target_model.predict(new_current_states)

    X = []
    Y = []
    for index, (observation, action, reward, new_observation, done) in enumerate(
        mini_batch
    ):
        if not done:
            max_future_q = reward + discount_factor * np.max(future_qs_list[index])
        else:
            max_future_q = reward

        current_qs = current_qs_list[index]
        current_qs[action] = (1 - learning_rate) * current_qs[
            action
        ] + learning_rate * max_future_q

        X.append(observation)
        Y.append(current_qs)
    model.fit(np.array(X), np.array(Y), batch_size=batch_size, verbose=0, shuffle=True)


def main():
    epsilon = 1
    max_epsilon = 1
    min_epsilon = 0.01
    decay = 0.01

    model = agent(env.observation_space.shape, env.action_space.n)
    target_model = agent(env.observation_space.shape, env.action_space.n)
    target_model.set_weights(model.get_weights())

    replay_memory = deque(maxlen=50_000)

    rewards = []

    steps_to_update_target_model = 0

    for episode in range(train_episodes):
        total_training_rewards = 0
        observation = env.reset(seed=RANDOM_SEED)[0]
        done = False

        while not done:
            steps_to_update_target_model += 1
            if True:
                env.render()

            random_number = np.random.rand()

            legal_actions = list(
                c
                for c in env.game_state["handCardIds"]
                if env.engine.is_card_usable(env.game_state, c)
            )

            if len(legal_actions) == 0:
                action = None
            elif random_number <= epsilon:
                action = random.choice(legal_actions)
            else:
                encoded = observation
                encoded_reshaped = np.reshape(
                    encoded, [1, env.observation_space.shape[0]]
                )
                predicted = model.predict(encoded_reshaped).flatten()

                legal_action_mask = np.zeros(len(SkillCards.get_all()))
                legal_action_mask[legal_actions] = 1

                masked_action = predicted * legal_action_mask
                action = masked_action.argmax()

            new_observation, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            replay_memory.append([observation, action, reward, new_observation, done])

            if steps_to_update_target_model % 4 == 0 or done:
                train(env, replay_memory, model, target_model, done)

            observation = new_observation
            total_training_rewards += reward

            if done:
                print(
                    "Total training rewards: {} after n steps = {} with final reward = {}".format(
                        total_training_rewards, episode, reward
                    )
                )
                rewards.append(total_training_rewards)
                total_training_rewards += 1

                if steps_to_update_target_model >= 100:
                    print("Copying main network weights to the target network weights")
                    target_model.set_weights(model.get_weights())
                    steps_to_update_target_model = 0
                break

        epsilon = min_epsilon + (max_epsilon - min_epsilon) * np.exp(-decay * episode)
    env.close()

    plt.figure(figsize=(10, 6))
    plt.plot(rewards, label="Q-learning Train")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")
    plt.title("Q-Learning (Episode vs Rewards)")
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()
