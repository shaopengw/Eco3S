# import numpy
import numpy as np
import matplotlib.pyplot as plt

# Using power() method
n = 100
gfg = np.random.power(a=6.5, size=(n, n))

plt.figure()
plt.hist(gfg, bins = 50, density = True)
plt.show()
