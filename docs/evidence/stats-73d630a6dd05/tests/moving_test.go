package stats

import (
	"errors"
	"math"
	"testing"
)

func movingApproxEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.Abs(a[i]-b[i]) > eps {
			return false
		}
	}
	return true
}

func TestMovingMax(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", []float64{}, 3, nil, ErrEmptyInput},
		{"window zero", []float64{1, 2, 3}, 0, nil, ErrBounds},
		{"window too large", []float64{1, 2, 3}, 5, nil, ErrBounds},
		{"normal case", []float64{1, 3, 2, 5, 4}, 3, []float64{3, 5, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMax(Float64Data(tc.input), tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil && !movingApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMedian(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", []float64{}, 2, nil, ErrEmptyInput},
		{"window zero", []float64{1, 2}, 0, nil, ErrBounds},
		{"window too large", []float64{1, 2}, 3, nil, ErrBounds},
		{"normal case", []float64{1, 3, 2, 5, 4}, 3, []float64{2, 3, 4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMedian(Float64Data(tc.input), tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil && !movingApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMin(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", []float64{}, 2, nil, ErrEmptyInput},
		{"window zero", []float64{5, 1}, 0, nil, ErrBounds},
		{"window too large", []float64{5, 1}, 4, nil, ErrBounds},
		{"normal case", []float64{1, 3, 2, 5, 4}, 3, []float64{1, 2, 2}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMin(Float64Data(tc.input), tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil && !movingApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingSum(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", []float64{}, 1, nil, ErrEmptyInput},
		{"window zero", []float64{2, 4}, 0, nil, ErrBounds},
		{"window too large", []float64{2, 4}, 5, nil, ErrBounds},
		{"normal case", []float64{1, 3, 2, 5, 4}, 3, []float64{6, 10, 11}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingSum(Float64Data(tc.input), tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil && !movingApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MovingMax(t *testing.T) {
	input := Float64Data{1, 3, 2, 5, 4}
	window := 3
	want := []float64{3, 5, 5}
	got, err := input.MovingMax(window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !movingApproxEqual(got, want) {
		t.Fatalf("unexpected result: got %v, want %v", got, want)
	}
}

func TestFloat64Data_MovingSum(t *testing.T) {
	cases := []struct {
		name   string
		data   []float64
		window int
	}{
		{"empty", []float64{}, 3},
		{"single", []float64{5}, 1},
		{"window larger than data", []float64{1, 2}, 5},
		{"normal", []float64{1, 2, 3, 4}, 2},
		{"invalid window", []float64{1, 2, 3}, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			// method call
			gotMethod, errMethod := Float64Data(tc.data).MovingSum(tc.window)
			// package‑level call
			gotFunc, errFunc := MovingSum(tc.data, tc.window)
			if (errMethod != nil) != (errFunc != nil) {
				t.Fatalf("error mismatch: method %v, func %v", errMethod, errFunc)
			}
			if errMethod != nil {
				// both returned an error, nothing more to check
				return
			}
			if !movingApproxEqual(gotMethod, gotFunc) {
				t.Fatalf("result mismatch: method %v, func %v", gotMethod, gotFunc)
			}
		})
	}
}

func TestFloat64Data_MovingMin(t *testing.T) {
	cases := []struct {
		name   string
		data   []float64
		window int
	}{
		{"empty", []float64{}, 3},
		{"single", []float64{7}, 1},
		{"window larger than data", []float64{3, 1}, 5},
		{"normal", []float64{5, 2, 8, 1, 4}, 3},
		{"invalid window", []float64{2, 3}, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotMethod, errMethod := Float64Data(tc.data).MovingMin(tc.window)
			gotFunc, errFunc := MovingMin(tc.data, tc.window)
			if (errMethod != nil) != (errFunc != nil) {
				t.Fatalf("error mismatch: method %v, func %v", errMethod, errFunc)
			}
			if errMethod != nil {
				return
			}
			if !movingApproxEqual(gotMethod, gotFunc) {
				t.Fatalf("result mismatch: method %v, func %v", gotMethod, gotFunc)
			}
		})
	}
}

func TestFloat64Data_MovingMedian(t *testing.T) {
	cases := []struct {
		name   string
		data   []float64
		window int
	}{
		{"empty", []float64{}, 3},
		{"single", []float64{9}, 1},
		{"window larger than data", []float64{4, 2}, 5},
		{"normal odd window", []float64{1, 3, 2, 5, 4}, 3},
		{"normal even window", []float64{10, 20, 30, 40}, 2},
		{"invalid window", []float64{1, 2, 3}, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotMethod, errMethod := Float64Data(tc.data).MovingMedian(tc.window)
			gotFunc, errFunc := MovingMedian(tc.data, tc.window)
			if (errMethod != nil) != (errFunc != nil) {
				t.Fatalf("error mismatch: method %v, func %v", errMethod, errFunc)
			}
			if errMethod != nil {
				return
			}
			if !movingApproxEqual(gotMethod, gotFunc) {
				t.Fatalf("result mismatch: method %v, func %v", gotMethod, gotFunc)
			}
		})
	}
}
