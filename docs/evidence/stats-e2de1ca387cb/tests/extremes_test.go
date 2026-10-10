package stats

import (
	"errors"
	"testing"
)

func TestArgMax_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{5}, 0, nil},
		{"multiple", Float64Data{1, 3, 2, 3, 0}, 1, nil}, // tie, first occurrence
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := ArgMax(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && gotIdx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestArgMin_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{7}, 0, nil},
		{"multiple", Float64Data{4, 2, 5, 2, 9}, 1, nil}, // tie, first occurrence
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := ArgMin(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && gotIdx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestFloat64Data_ArgMaxAndArgMin_Wrappers(t *testing.T) {
	data := Float64Data{8, 3, 8, 1}
	// ArgMax wrapper should return first max index (0)
	if idx, err := data.ArgMax(); err != nil || idx != 0 {
		t.Fatalf("Float64Data.ArgMax expected (0, nil), got (%d, %v)", idx, err)
	}
	// ArgMin wrapper should return index of minimum (3)
	if idx, err := data.ArgMin(); err != nil || idx != 3 {
		t.Fatalf("Float64Data.ArgMin expected (3, nil), got (%d, %v)", idx, err)
	}
	// Empty slice wrappers should propagate ErrEmptyInput
	empty := Float64Data{}
	if _, err := empty.ArgMax(); !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("Float64Data.ArgMax on empty expected ErrEmptyInput, got %v", err)
	}
	if _, err := empty.ArgMin(); !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("Float64Data.ArgMin on empty expected ErrEmptyInput, got %v", err)
	}
}

func TestRange_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, 0, ErrEmptyInput},
		{"normal", Float64Data{2, 5, 1, 4}, 4, nil}, // max 5, min 1 => range 4
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Range(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && got != tc.want {
				t.Fatalf("expected range %v, got %v", tc.want, got)
			}
		})
	}
}
