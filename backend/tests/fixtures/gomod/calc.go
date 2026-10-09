package calc

import "errors"

// ErrNegative is returned for negative input.
var ErrNegative = errors.New("negative input")

// Abs returns the absolute value of x.
func Abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// Sqrt returns the integer square root of x.
func Sqrt(x int) (int, error) {
	if x < 0 {
		return 0, ErrNegative
	}
	r := 0
	for (r+1)*(r+1) <= x {
		r++
	}
	return r, nil
}
