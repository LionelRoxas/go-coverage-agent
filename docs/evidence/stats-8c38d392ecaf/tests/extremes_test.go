package stats

import (
	"testing"
)

func TestArgMax_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{5.0}, 0, nil},
		{"multiple", Float64Data{1.0, 3.0, 2.0, 3.0, 0.0}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := ArgMax(tc.input)
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if gotIdx != tc.wantIdx {
				t.Errorf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestArgMin_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{5.0}, 0, nil},
		{"multiple", Float64Data{2.0, 1.0, 3.0, 1.0, 4.0}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := ArgMin(tc.input)
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if gotIdx != tc.wantIdx {
				t.Errorf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestFloat64Data_ArgMax(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{7.0}, 0, nil},
		{"multiple", Float64Data{4.0, 9.0, 2.0, 9.0}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := tc.data.ArgMax()
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if gotIdx != tc.wantIdx {
				t.Errorf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestFloat64Data_ArgMin(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantIdx int
		wantErr error
	}{
		{"empty", Float64Data{}, -1, ErrEmptyInput},
		{"single", Float64Data{7.0}, 0, nil},
		{"multiple", Float64Data{5.0, 2.0, 8.0, 2.0}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotIdx, err := tc.data.ArgMin()
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if gotIdx != tc.wantIdx {
				t.Errorf("expected index %d, got %d", tc.wantIdx, gotIdx)
			}
		})
	}
}

func TestFloat64Data_Range(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, 0, ErrEmptyInput},
		{"single", Float64Data{3.5}, 0, nil},
		{"multiple", Float64Data{1.0, 4.0, -2.0, 5.5}, 7.5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Range()
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if got != tc.want {
					t.Errorf("expected range %v, got %v", tc.want, got)
				}
			}
		})
	}
}
