from __future__ import division

import pytest
import numpy as np
from scipy import sparse

from sklearn.datasets import load_iris

from imblearn.datasets import make_imbalance
from imblearn.under_sampling import NearMiss

from imblearn.tensorflow import balanced_batch_generator

tf = pytest.importorskip('tensorflow')


@pytest.mark.parametrize("sampler", [None, NearMiss()])
def test_balanced_batch_generator(sampler):
    X, y = load_iris(return_X_y=True)
    X, y = make_imbalance(X, y, {0: 30, 1: 50, 2: 40})
    X = X.astype(np.float32)

    batch_size = 10
    training_generator, steps_per_epoch = balanced_batch_generator(
        X, y, sample_weight=None, sampler=sampler,
        batch_size=batch_size, random_state=42)

    learning_rate = 0.01
    epochs = 10
    input_size = X.shape[1]
    output_size = 3

    # helper functions
    def init_weights(shape):
        return tf.Variable(tf.random_normal(shape, stddev=0.01))

    def accuracy(y_true, y_pred):
        return np.mean(np.argmax(y_pred, axis=1) == y_true)

    # input and output
    data = tf.placeholder("float32", shape=[None, input_size])
    targets = tf.placeholder("int32", shape=[None])

    # build the model and weights
    W = init_weights([input_size, output_size])
    b = init_weights([output_size])
    out_act = tf.nn.sigmoid(tf.matmul(data, W) + b)

    # build the loss, predict, and train operator
    cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
        logits=out_act, labels=targets)
    loss = tf.reduce_sum(cross_entropy)
    optimizer = tf.train.GradientDescentOptimizer(learning_rate)
    train_op = optimizer.minimize(loss)
    predict = tf.nn.softmax(out_act)

    # Initialization of all variables in the graph
    init = tf.global_variables_initializer()

    with tf.Session() as sess:
        sess.run(init)

        for e in range(epochs):
            for i in range(steps_per_epoch):
                X_batch, y_batch = next(training_generator)
                sess.run([train_op, loss],
                         feed_dict={data: X_batch, targets: y_batch})

            # For each epoch, run accuracy on train and test
            predicts_train = sess.run(predict, feed_dict={data: X})
            print("epoch: {} train accuracy: {:.3f}"
                  .format(e, accuracy(y, predicts_train)))


@pytest.mark.parametrize("is_sparse", [True, False])
def test_balanced_batch_generator_function_sparse(is_sparse):
    X, y = load_iris(return_X_y=True)
    X, y = make_imbalance(X, y, {0: 30, 1: 50, 2: 40})
    X = X.astype(np.float32)

    training_generator, steps_per_epoch = balanced_batch_generator(
        sparse.csr_matrix(X), y, sparse=is_sparse, batch_size=10,
        random_state=42)
    for idx in range(steps_per_epoch):
        X_batch, y_batch = next(training_generator)
        if is_sparse:
            assert sparse.issparse(X_batch)
        else:
            assert not sparse.issparse(X_batch)
