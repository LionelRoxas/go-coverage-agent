package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestMovingMax_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 3, ErrEmptyInput},
		{"window zero", Float64Data{1, 2, 3}, 0, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 5, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingMax(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingMax_Normal(t *testing.T) {
	input := Float64Data{1, 3, 2, 5, 4}
	window := 3
	want := []float64{3, 5, 5}
	got, err := MovingMax(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestMovingMedian_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, ErrEmptyInput},
		{"window zero", Float64Data{1, 2}, 0, ErrBounds},
		{"window too large", Float64Data{1, 2}, 3, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingMedian(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingMedian_Normal(t *testing.T) {
	input := Float64Data{1, 3, 2, 5, 4}
	window := 3
	want := []float64{2, 3, 4}
	got, err := MovingMedian(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestMovingMin_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 1, ErrEmptyInput},
		{"window zero", Float64Data{1}, 0, ErrBounds},
		{"window too large", Float64Data{1}, 2, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingMin(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingMin_Normal(t *testing.T) {
	input := Float64Data{1, 3, 2, 5, 4}
	window := 3
	want := []float64{1, 2, 2}
	got, err := MovingMin(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestMovingSum_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 1, ErrEmptyInput},
		{"window zero", Float64Data{1, 2}, 0, ErrBounds},
		{"window too large", Float64Data{1, 2}, 3, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingSum(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingSum_Normal(t *testing.T) {
	input := Float64Data{1, 3, 2, 5, 4}
	window := 3
	want := []float64{6, 10, 11}
	got, err := MovingSum(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestFloat64Data_MovingMax(t *testing.T) {
	input := Float64Data{2, 1, 4, 3}
	window := 2
	want := []float64{2, 4, 4}
	got, err := input.MovingMax(window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}
