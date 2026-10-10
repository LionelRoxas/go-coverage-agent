package stats

import (
	"errors"
	"math"
	"testing"
)

func float64ApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestCovariance_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		d1   Float64Data
		d2   Float64Data
		want float64
		err  error
	}{{
		name: "empty first input",
		d1:   Float64Data{},
		d2:   Float64Data{1, 2, 3},
		want: math.NaN(),
		err:  EmptyInputErr,
	}, {
		name: "size mismatch",
		d1:   Float64Data{1, 2},
		d2:   Float64Data{1, 2, 3},
		want: math.NaN(),
		err:  SizeErr,
	}, {
		name: "simple positive numbers",
		d1:   Float64Data{1, 2, 3},
		d2:   Float64Data{4, 5, 6},
		want: 1.0,
		err:  nil,
	}, {
		name: "negative and positive mix",
		d1:   Float64Data{-1, 0, 1},
		d2:   Float64Data{2, 0, -2},
		want: -2.0,
		err:  nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Covariance(tc.d1, tc.d2)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !float64ApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestCovariancePopulation_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		d1   Float64Data
		d2   Float64Data
		want float64
		err  error
	}{{
		name: "empty second input",
		d1:   Float64Data{1, 2, 3},
		d2:   Float64Data{},
		want: math.NaN(),
		err:  EmptyInputErr,
	}, {
		name: "size mismatch",
		d1:   Float64Data{1, 2, 3},
		d2:   Float64Data{1, 2},
		want: math.NaN(),
		err:  SizeErr,
	}, {
		name: "simple case",
		d1:   Float64Data{1, 2, 3},
		d2:   Float64Data{4, 5, 6},
		want: 2.0 / 3.0,
		err:  nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CovariancePopulation(tc.d1, tc.d2)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !float64ApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestPopulationVariance_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
		want float64
		err  error
	}{{
		name: "empty input",
		data: Float64Data{},
		want: math.NaN(),
		err:  EmptyInputErr,
	}, {
		name: "simple dataset",
		data: Float64Data{1, 2, 3, 4},
		want: 5.0 / 4.0,
		err:  nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationVariance(tc.data)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !float64ApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestSampleVariance_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
		want float64
		err  error
	}{{
		name: "empty input",
		data: Float64Data{},
		want: math.NaN(),
		err:  EmptyInputErr,
	}, {
		name: "simple dataset",
		data: Float64Data{1, 2, 3, 4},
		want: 5.0 / 3.0,
		err:  nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleVariance(tc.data)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !float64ApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestVariance_Uncovered(t *testing.T) {
	data := Float64Data{2, 4, 6, 8}
	pop, err1 := PopulationVariance(data)
	if err1 != nil {
		t.Fatalf("population variance error: %v", err1)
	}
	got, err2 := Variance(data)
	if err2 != nil {
		t.Fatalf("variance wrapper error: %v", err2)
	}
	if !float64ApproxEqual(got, pop) {
		t.Fatalf("Variance wrapper returned %v, want %v", got, pop)
	}
}
